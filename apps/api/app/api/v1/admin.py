import json
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Query, Request, UploadFile
from pydantic import BaseModel, Field, HttpUrl
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.v1.documents import doc_detail
from app.core import audit
from app.core.db import get_db
from app.core.errors import AppError, not_found
from app.core.security import ROLES, require
from app.models import AuditEvent, Document, IngestionJob, Role, SimModel, User
from app.services.ingestion.pipeline import _clean_meta, enqueue, register_upload
from app.services.ingestion.urlfetch import fetch_url
from app.services.retrieval.index import invalidate_index
from app.services.retrieval.search import clear_search_cache

router = APIRouter(prefix="/admin", tags=["admin"])


def _parse_meta(raw: str) -> dict:
    try:
        meta = json.loads(raw or "{}")
        if not isinstance(meta, dict):
            raise ValueError
        return meta
    except ValueError:
        raise AppError(422, "INVALID_METADATA", "metadata must be a JSON object.")


def _job_out(j: IngestionJob) -> dict:
    return {"id": str(j.id), "document_id": str(j.document_id), "status": j.status, "stage": j.stage, "error": j.error,
            "stats": {k: v for k, v in j.stats.items() if k not in ("version_id", "explicit")}}


@router.post("/documents/ingest", status_code=202)
async def ingest(request: Request, background: BackgroundTasks, file: UploadFile = File(...), metadata: str = Form("{}"),
                 document_id: uuid.UUID | None = Form(None), db: Session = Depends(get_db), user: User = Depends(require("admin.manage"))):
    data = await file.read(15 * 1024 * 1024 + 1)  # bounded read; validate_upload enforces the configured cap
    doc, job = register_upload(db, filename=file.filename or "upload", data=data, metadata=_parse_meta(metadata),
                               actor=user, document_id=document_id)
    audit.record(db, request, user, "DOCUMENT_UPLOADED", "document", doc.id, {"job_id": str(job.id), "bytes": len(data),
                                                                             "sha256": None if not doc.versions else None})
    enqueue(job.id, background)
    return {"document_id": str(doc.id), "job": _job_out(job)}


class UrlIn(BaseModel):
    url: HttpUrl
    metadata: dict = Field(default_factory=dict)


@router.post("/documents/ingest-url", status_code=202)
def ingest_url(body: UrlIn, request: Request, background: BackgroundTasks, db: Session = Depends(get_db),
               user: User = Depends(require("admin.manage"))):
    fname, data = fetch_url(str(body.url))
    meta = {"source_url": str(body.url), **body.metadata}
    doc, job = register_upload(db, filename=fname, data=data, metadata=meta, actor=user)
    audit.record(db, request, user, "DOCUMENT_UPLOADED", "document", doc.id, {"job_id": str(job.id), "via": "url", "bytes": len(data)})
    enqueue(job.id, background)
    return {"document_id": str(doc.id), "job": _job_out(job)}


@router.get("/ingestion/{job_id}")
def ingestion_status(job_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(require("admin.manage"))):
    j = db.get(IngestionJob, job_id)
    if not j:
        raise not_found("Ingestion job")
    return _job_out(j)


@router.get("/documents")
def list_documents(status: str | None = None, db: Session = Depends(get_db), user: User = Depends(require("evidence.review"))):
    q = select(Document).where(Document.deleted_at.is_(None)).order_by(Document.created_at.desc())
    if status:
        q = q.where(Document.status == status)
    out = []
    for d in db.scalars(q):
        job = db.scalar(select(IngestionJob).where(IngestionJob.document_id == d.id).order_by(IngestionJob.created_at.desc()))
        out.append({**doc_detail(d, db), "job": _job_out(job) if job else None})
    return out


def _review(db: Session, request: Request, doc_id: uuid.UUID, user: User, approve: bool) -> dict:
    d = db.get(Document, doc_id)
    if not d or d.deleted_at:
        raise not_found("Document")
    if d.status not in ("pending_review", "approved", "rejected"):
        raise AppError(409, "NOT_REVIEWABLE", f"Document is '{d.status}' and cannot be reviewed yet.")
    d.status = "approved" if approve else "rejected"
    d.approved_by, d.approved_at = (user.id, datetime.now(UTC)) if approve else (None, None)
    db.commit()
    invalidate_index()
    clear_search_cache()
    audit.record(db, request, user, "DOCUMENT_APPROVED" if approve else "DOCUMENT_REJECTED", "document", d.id)
    return doc_detail(d, db)


@router.post("/documents/{doc_id}/approve")
def approve(doc_id: uuid.UUID, request: Request, db: Session = Depends(get_db), user: User = Depends(require("evidence.review"))):
    return _review(db, request, doc_id, user, True)


@router.post("/documents/{doc_id}/reject")
def reject(doc_id: uuid.UUID, request: Request, db: Session = Depends(get_db), user: User = Depends(require("evidence.review"))):
    return _review(db, request, doc_id, user, False)


class MetaPatch(BaseModel):
    title: str | None = Field(default=None, max_length=500)
    organization: str | None = Field(default=None, max_length=255)
    document_type: str | None = None
    authority_level: str | None = None
    access_level: str | None = None
    state_code: str | None = Field(default=None, max_length=5)
    publication_date: str | None = None
    source_url: str | None = Field(default=None, max_length=1000)


@router.patch("/documents/{doc_id}")
def patch_document(doc_id: uuid.UUID, body: MetaPatch, db: Session = Depends(get_db), user: User = Depends(require("admin.manage"))):
    d = db.get(Document, doc_id)
    if not d or d.deleted_at:
        raise not_found("Document")
    for k, v in _clean_meta(body.model_dump(exclude_none=True)).items():
        setattr(d, k, v)
    db.commit()
    invalidate_index()
    clear_search_cache()
    return doc_detail(d, db)


# ---- users ----
@router.get("/users")
def users(db: Session = Depends(get_db), user: User = Depends(require("admin.manage"))):
    return [{"id": str(u.id), "name": u.name, "email": u.email, "role": u.role.name, "status": u.status}
            for u in db.scalars(select(User).order_by(User.created_at))]


class RoleIn(BaseModel):
    role: str


@router.patch("/users/{uid}/role")
def set_role(uid: uuid.UUID, body: RoleIn, request: Request, db: Session = Depends(get_db), user: User = Depends(require("admin.manage"))):
    if body.role not in ROLES or body.role == "public":
        raise AppError(422, "INVALID_ROLE", f"role must be one of {[r for r in ROLES if r != 'public']}")
    u = db.get(User, uid)
    if not u:
        raise not_found("User")
    if u.id == user.id:
        raise AppError(409, "SELF_ROLE_CHANGE", "Admins cannot change their own role.")
    old = u.role.name
    u.role_id = db.scalar(select(Role.id).where(Role.name == body.role))
    db.commit()
    audit.record(db, request, user, "USER_ROLE_CHANGED", "user", u.id, {"from": old, "to": body.role})
    return {"id": str(u.id), "role": body.role}


# ---- models (governed: edits create a new version, never mutate silently) ----
class ModelPatch(BaseModel):
    coefficients: dict[str, float] = Field(default_factory=dict)
    change_note: str = Field(min_length=5, max_length=1000)


@router.patch("/models/{mid}")
def update_model(mid: uuid.UUID, body: ModelPatch, request: Request, db: Session = Depends(get_db),
                 user: User = Depends(require("admin.manage"))):
    m = db.get(SimModel, mid)
    if not m:
        raise not_found("Model")
    unknown = set(body.coefficients) - set(m.definition["coefficients"])
    if unknown:
        raise AppError(422, "UNKNOWN_COEFFICIENT", f"Unknown coefficient(s): {sorted(unknown)}")
    new = json.loads(json.dumps(m.definition))
    new["coefficients"].update(body.coefficients)
    c = new["coefficients"]
    if abs(c["w_coverage"] + c["w_workload"] + c["w_dispute"] - 1.0) > 1e-6:
        raise AppError(422, "WEIGHTS_MUST_SUM_TO_ONE", "Composite weights must sum to 1.")
    major, minor, patch = (int(x) for x in m.version.split("."))
    new["version"] = f"{major}.{minor}.{patch + 1}"
    for k in body.coefficients:
        new["coefficient_provenance"][k] = f"Changed by {user.email} from {m.definition['coefficients'][k]} — {body.change_note}"
    nm = SimModel(key=m.key, name=m.name, version=new["version"], description=m.description, methodology=m.methodology,
                  status="active", definition=new, review_status="unreviewed")
    m.status = "deprecated"
    db.add(nm)
    db.commit()
    audit.record(db, request, user, "MODEL_UPDATED", "model", nm.id, {"from_version": m.version, "to_version": nm.version,
                                                                    "changed": sorted(body.coefficients)})
    return {"id": str(nm.id), "version": nm.version}


class ReviewIn(BaseModel):
    status: str = Field(pattern="^(approved_for_demo|needs_changes|rejected)$")
    notes: str = Field(min_length=5, max_length=2000)


@router.post("/models/{mid}/review")
def review_model(mid: uuid.UUID, body: ReviewIn, request: Request, db: Session = Depends(get_db),
                 user: User = Depends(require("model.review"))):
    m = db.get(SimModel, mid)
    if not m:
        raise not_found("Model")
    m.review_status, m.review_notes, m.reviewed_by, m.reviewed_at = body.status, body.notes, user.id, datetime.now(UTC)
    db.commit()
    audit.record(db, request, user, "MODEL_REVIEWED", "model", m.id, {"status": body.status})
    return {"id": str(m.id), "review_status": m.review_status}


@router.get("/models")
def admin_models(db: Session = Depends(get_db), user: User = Depends(require("model.review"))):
    return [{"id": str(m.id), "key": m.key, "name": m.name, "version": m.version, "status": m.status,
             "review_status": m.review_status, "review_notes": m.review_notes, "coefficients": m.definition["coefficients"],
             "coefficient_provenance": m.definition["coefficient_provenance"]}
            for m in db.scalars(select(SimModel).order_by(SimModel.key, SimModel.created_at.desc()))]


# ---- audit ----
@router.get("/audit")
def audit_log(action: str | None = None, limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
              db: Session = Depends(get_db), user: User = Depends(require("admin.manage"))):
    q = select(AuditEvent).order_by(AuditEvent.created_at.desc())
    if action:
        q = q.where(AuditEvent.action == action)
    total = db.scalar(select(func.count()).select_from(q.subquery()))
    rows = db.scalars(q.limit(limit).offset(offset)).all()
    emails = {u.id: u.email for u in db.scalars(select(User).where(User.id.in_([r.actor_id for r in rows if r.actor_id])))}
    return {"total": total, "events": [{"id": str(r.id), "action": r.action, "actor": emails.get(r.actor_id, "anonymous"),
                                        "actor_role": r.actor_role, "entity_type": r.entity_type, "entity_id": r.entity_id,
                                        "ip": r.ip, "user_agent": r.user_agent[:80], "meta": r.meta,
                                        "created_at": r.created_at.isoformat()} for r in rows]}
