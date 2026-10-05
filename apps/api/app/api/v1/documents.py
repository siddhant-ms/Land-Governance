import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import audit
from app.core.db import get_db
from app.core.errors import AppError, not_found
from app.core.security import can_access, current_user, optional_user, require, role_of
from app.models import Annotation, Document, DocumentChunk, DocumentVersion, User
from pydantic import BaseModel, Field

from app.services.retrieval.search import search_evidence

router = APIRouter(prefix="/documents", tags=["documents"])


def load_document(db: Session, doc_id: uuid.UUID, user: User | None, request: Request | None = None) -> Document:
    doc = db.get(Document, doc_id)
    role = role_of(user)
    if not doc or doc.deleted_at:
        raise not_found("Document")
    privileged = role in ("admin", "expert")
    if doc.status != "approved" and not privileged:
        raise not_found("Document")  # unapproved documents are invisible to everyone else
    if not can_access(role, doc.access_level):
        audit.record(db, request, user, "RESTRICTED_DOCUMENT_DENIED", "document", doc.id)
        raise AppError(403, "RESTRICTED_DOCUMENT",
                       "This document exists in the repository but is restricted to authorized users.", {"document_id": str(doc.id)})
    return doc


def doc_detail(doc: Document, db: Session) -> dict:
    ver = db.scalar(select(DocumentVersion).where(DocumentVersion.document_id == doc.id, DocumentVersion.is_current))
    return {"id": str(doc.id), "title": doc.title, "authors": doc.authors, "organization": doc.organization,
            "source_url": doc.source_url, "document_type": doc.document_type, "authority_level": doc.authority_level,
            "language": doc.language, "publication_date": doc.publication_date.isoformat() if doc.publication_date else None,
            "state_code": doc.state_code, "geography": doc.geography_label, "access_level": doc.access_level,
            "status": doc.status, "is_demo": doc.is_demo, "provenance_note": doc.provenance_note,
            "topics": [t.name for t in doc.topics], "extraction_quality": doc.extraction_quality,
            "version": {"version_no": ver.version_no, "content_hash": ver.content_hash, "pages": ver.page_count} if ver else None}


@router.get("/{doc_id}")
def get_document(doc_id: uuid.UUID, request: Request, db: Session = Depends(get_db), user: User | None = Depends(optional_user)):
    doc = load_document(db, doc_id, user, request)
    audit.record(db, request, user, "DOCUMENT_VIEWED", "document", doc.id)
    chunks = db.scalars(select(DocumentChunk).join(DocumentVersion, DocumentVersion.id == DocumentChunk.document_version_id)
                        .where(DocumentChunk.document_id == doc.id, DocumentVersion.is_current)
                        .order_by(DocumentChunk.chunk_index)).all()
    return {**doc_detail(doc, db), "chunks": [{"id": str(c.id), "index": c.chunk_index, "page": c.page_no, "section": c.section,
                                                "text": c.text} for c in chunks]}


@router.get("/{doc_id}/chunks/{chunk_id}")
def get_chunk(doc_id: uuid.UUID, chunk_id: uuid.UUID, request: Request, db: Session = Depends(get_db),
              user: User | None = Depends(optional_user)):
    doc = load_document(db, doc_id, user, request)
    ch = db.get(DocumentChunk, chunk_id)
    if not ch or ch.document_id != doc.id:
        raise not_found("Passage")
    neighbours = db.scalars(select(DocumentChunk).where(DocumentChunk.document_version_id == ch.document_version_id,
                            DocumentChunk.chunk_index.in_([ch.chunk_index - 1, ch.chunk_index + 1]))).all()
    return {"chunk": {"id": str(ch.id), "page": ch.page_no, "section": ch.section, "text": ch.text, "index": ch.chunk_index,
                      "indexed_metadata": ch.meta}, "document": doc_detail(doc, db),
            "context": {"before": next((n.text for n in neighbours if n.chunk_index < ch.chunk_index), None),
                        "after": next((n.text for n in neighbours if n.chunk_index > ch.chunk_index), None)}}


@router.get("/{doc_id}/related")
def related(doc_id: uuid.UUID, request: Request, db: Session = Depends(get_db), user: User | None = Depends(optional_user)):
    doc = load_document(db, doc_id, user, request)
    out = search_evidence(db, f"{doc.title} {' '.join(t.name for t in doc.topics)}", None, role_of(user), top_k=40)
    seen, res = {str(doc.id)}, []
    for h in out.hits:
        if h.document_id in seen:
            continue
        seen.add(h.document_id)
        shared = sorted(set(h.doc["topics"]) & {t.name for t in doc.topics})
        res.append({"document_id": h.document_id, "title": h.doc["title"], "document_type": h.doc["document_type"],
                    "year": h.doc["publication_date"].year if h.doc["publication_date"] else None,
                    "is_demo": h.doc["is_demo"], "similarity": round(h.relevance, 3), "shared_topics": shared})
        if len(res) >= 5:
            break
    return {"related": res, "basis": "Semantic/lexical similarity of title and topics; shared topic tags shown."}


class AnnotationIn(BaseModel):
    text: str = Field(min_length=3, max_length=2000)
    kind: str = Field(default="comment", pattern="^(comment|flag|verified)$")
    chunk_id: uuid.UUID | None = None


@router.post("/{doc_id}/annotations", status_code=201)
def annotate(doc_id: uuid.UUID, body: AnnotationIn, request: Request, db: Session = Depends(get_db),
             user: User = Depends(require("evidence.review"))):
    doc = load_document(db, doc_id, user, request)
    a = Annotation(document_id=doc.id, chunk_id=body.chunk_id, author_id=user.id, kind=body.kind, text=body.text)
    db.add(a)
    db.commit()
    audit.record(db, request, user, "ANNOTATION_ADDED", "document", doc.id, {"kind": body.kind})
    return {"id": str(a.id)}


@router.get("/{doc_id}/annotations")
def list_annotations(doc_id: uuid.UUID, request: Request, db: Session = Depends(get_db), user: User = Depends(require("evidence.review"))):
    load_document(db, doc_id, user, request)
    rows = db.scalars(select(Annotation).where(Annotation.document_id == doc_id).order_by(Annotation.created_at)).all()
    return [{"id": str(a.id), "kind": a.kind, "text": a.text, "chunk_id": str(a.chunk_id) if a.chunk_id else None,
             "author_id": str(a.author_id), "created_at": a.created_at.isoformat()} for a in rows]
