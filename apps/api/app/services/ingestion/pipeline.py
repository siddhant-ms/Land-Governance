"""Document -> Validation -> Extraction -> Metadata -> Chunking -> Embedding -> Indexing -> Searchable."""
import hashlib
import logging
import re
import uuid
from datetime import UTC, date, datetime
from pathlib import Path

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import SessionLocal
from app.core.errors import AppError
from app.models import Document, DocumentChunk, DocumentTopic, DocumentVersion, IngestionJob, Topic, User
from app.providers.embeddings import get_embedding_provider
from app.providers.storage import get_store
from app.services.ingestion.chunking import chunk_pages
from app.services.ingestion.extract import extract, validate_upload
from app.services.retrieval.index import invalidate_index

log = logging.getLogger(__name__)

DOC_FIELDS = ("title", "authors", "organization", "source_url", "document_type", "authority_level", "language",
              "publication_date", "state_code", "district_code", "geography_label", "access_level",
              "is_demo", "provenance_note")
DOCUMENT_TYPES = {"policy_report", "research_paper", "legal_text", "case_study", "dataset_description", "brief"}
AUTHORITY_LEVELS = {"official", "peer_reviewed", "institutional", "demo"}


def _clean_meta(meta: dict) -> dict:
    out = {k: v for k, v in meta.items() if k in DOC_FIELDS or k == "topics"}
    if out.get("document_type") and out["document_type"] not in DOCUMENT_TYPES:
        raise AppError(422, "INVALID_METADATA", f"document_type must be one of {sorted(DOCUMENT_TYPES)}")
    if out.get("authority_level") and out["authority_level"] not in AUTHORITY_LEVELS:
        raise AppError(422, "INVALID_METADATA", f"authority_level must be one of {sorted(AUTHORITY_LEVELS)}")
    if out.get("access_level") and out["access_level"] not in ("public", "restricted", "internal"):
        raise AppError(422, "INVALID_METADATA", "access_level must be public, restricted or internal")
    if isinstance(out.get("publication_date"), str):
        m = re.match(r"(\d{4})(?:-(\d{2}))?(?:-(\d{2}))?", out["publication_date"])
        if not m:
            raise AppError(422, "INVALID_METADATA", "publication_date must be YYYY[-MM[-DD]]")
        out["publication_date"] = date(int(m[1]), int(m[2] or 1), int(m[3] or 1))
    return out


def _set_topics(db: Session, doc: Document, names: list[str]) -> None:
    db.execute(delete(DocumentTopic).where(DocumentTopic.document_id == doc.id))
    for name in {n.strip() for n in names if n and n.strip()}:
        t = db.scalar(select(Topic).where(Topic.name == name))
        if not t:
            t = Topic(name=name)
            db.add(t)
            db.flush()
        db.add(DocumentTopic(document_id=doc.id, topic_id=t.id))


def register_upload(db: Session, *, filename: str, data: bytes, metadata: dict, actor: User | None,
                    document_id: uuid.UUID | None = None, auto_approve: bool = False) -> tuple[Document, IngestionJob]:
    """Synchronous, cheap part: validate, hash, store, create rows. Heavy work happens in process_job."""
    s = get_settings()
    ext = validate_upload(filename, data, s.max_upload_bytes)
    meta = _clean_meta(metadata)
    content_hash = hashlib.sha256(data).hexdigest()
    dup = db.scalar(select(DocumentVersion).where(DocumentVersion.content_hash == content_hash, DocumentVersion.is_current))
    if dup:
        raise AppError(409, "DUPLICATE_DOCUMENT", "An identical file is already in the repository.",
                       {"document_id": str(dup.document_id)})
    store = get_store()

    if document_id:
        doc = db.get(Document, document_id)
        if not doc or doc.deleted_at:
            raise AppError(404, "NOT_FOUND", "Document not found.")
        prev = db.scalar(select(DocumentVersion).where(DocumentVersion.document_id == doc.id, DocumentVersion.is_current))
        version_no = (db.scalar(select(func.max(DocumentVersion.version_no)).where(DocumentVersion.document_id == doc.id)) or 0) + 1
        if prev:  # never silently replace: old version stays, linked as parent
            prev.is_current = False
        doc.status = "processing"
        for k, v in meta.items():
            if k != "topics":
                setattr(doc, k, v)
    else:
        prev = None
        version_no = 1
        title_from_filename = "title" not in meta
        doc = Document(**{k: v for k, v in meta.items() if k != "topics"})
        if title_from_filename:
            doc.title = Path(filename).stem.replace("_", " ").replace("-", " ").strip().title()
        doc.status = "processing"
        doc.created_by = actor.id if actor else None
        db.add(doc)
        db.flush()
    if "topics" in meta:
        _set_topics(db, doc, meta["topics"])

    ver_id = uuid.uuid4()
    safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", Path(filename).name)[:80]
    uri = store.put(f"originals/{doc.id}/v{version_no}_{safe_name}", data)
    ver = DocumentVersion(id=ver_id, document_id=doc.id, version_no=version_no, content_hash=content_hash,
                          object_uri=uri, is_current=True, parent_version_id=prev.id if prev else None)
    db.add(ver)
    job = IngestionJob(document_id=doc.id, status="queued", stage="queued", created_by=actor.id if actor else None,
                       stats={"filename": safe_name, "ext": ext, "version_no": version_no,
                              "title_from_filename": (document_id is None and "title" not in meta),
                              "explicit": sorted(meta.keys()),
                              "auto_approve": auto_approve, "version_id": str(ver_id)})
    db.add(job)
    db.commit()
    return doc, job


def _stage(db: Session, job: IngestionJob, stage: str) -> None:
    job.stage, job.status = stage, "running"
    db.commit()


def process_job(job_id: uuid.UUID, session_factory=None) -> None:
    """Runs in a background worker. Never raises: failures are recorded on the job/document."""
    db: Session = (session_factory or SessionLocal)()
    job = db.get(IngestionJob, job_id)
    if not job:
        db.close()
        return
    doc = db.get(Document, job.document_id)
    try:
        ver = db.get(DocumentVersion, uuid.UUID(job.stats["version_id"]))
        store = get_store()
        _stage(db, job, "extracting")
        ex = extract(store.get(ver.object_uri), job.stats["ext"])
        if not ex.pages:
            raise AppError(422, "NO_TEXT", "; ".join(ex.warnings) or "No text could be extracted.")
        # metadata extraction: fields supplied explicitly at upload always win; file metadata fills the rest
        explicit = set(job.stats.get("explicit", []))
        for k, v in ex.metadata.items():
            if k == "topics" and "topics" not in explicit:
                _set_topics(db, doc, v)
            elif k in DOC_FIELDS and v not in (None, "", []) and k not in explicit:
                setattr(doc, k, v)
        doc.extraction_quality = ex.quality
        ver.page_count = len(ex.pages)
        ver.extracted_text_uri = store.put(f"extracted/{doc.id}/v{ver.version_no}.txt",
                                           "\n\f".join(t for _, t in ex.pages).encode())
        _stage(db, job, "chunking")
        chunks = chunk_pages(ex.pages)
        if not chunks:
            raise AppError(422, "NO_CHUNKS", "Document text was too short to index.")
        _stage(db, job, "embedding")
        provider = get_embedding_provider()
        vectors: list[list[float]] = []
        for i in range(0, len(chunks), 64):
            vectors.extend(provider.embed([c.text for c in chunks[i:i + 64]]))
        _stage(db, job, "indexing")
        db.execute(delete(DocumentChunk).where(DocumentChunk.document_version_id == ver.id))
        snapshot = {
            "title": doc.title, "organization": doc.organization, "publication_date":
                doc.publication_date.isoformat() if doc.publication_date else None,
            "document_type": doc.document_type, "state_code": doc.state_code, "district_code": doc.district_code,
            "geography": doc.geography_label, "source_url": doc.source_url,
        }
        for c, v in zip(chunks, vectors):
            db.add(DocumentChunk(document_id=doc.id, document_version_id=ver.id, chunk_index=c.index,
                                 page_no=c.page_no, section=c.section, text=c.text,
                                 token_count=len(c.text.split()), embedding=v, embedding_model=provider.name,
                                 meta=snapshot))
        # older versions' chunks stay for provenance but are excluded from search (is_current)
        auto = job.stats.get("auto_approve")
        doc.status = "approved" if auto else "pending_review"
        if auto:
            doc.approved_at = datetime.now(UTC)
        job.status, job.stage = "done", "done"
        job.stats = {**job.stats, "chunks": len(chunks), "pages": len(ex.pages), "quality": ex.quality,
                     "warnings": ex.warnings, "embedding_model": provider.name}
        db.commit()
        invalidate_index()
    except Exception as e:  # noqa: BLE001 - record any failure on the job, never crash the worker
        db.rollback()
        job = db.get(IngestionJob, job_id)
        doc = db.get(Document, job.document_id)
        job.status, job.stage = "failed", "failed"
        job.error = (e.message if isinstance(e, AppError) else f"{type(e).__name__}: {e}")[:1000]
        doc.status = "failed"
        db.commit()
        log.warning("ingestion failed job=%s err=%s", job_id, job.error)
    finally:
        db.close()


def enqueue(job_id: uuid.UUID, background=None) -> str:
    """Job runner abstraction: Celery when configured, otherwise FastAPI BackgroundTasks / inline."""
    s = get_settings()
    if s.job_backend == "celery":
        from app.worker import ingest_task
        ingest_task.delay(str(job_id))
        return "celery"
    if background is not None:
        background.add_task(process_job, job_id)
        return "background"
    process_job(job_id)
    return "inline"
