"""Append-only audit trail. Stores hashes/ids rather than free-text where possible (data minimisation)."""
import hashlib

from fastapi import Request
from sqlalchemy.orm import Session

from app.core.security import role_of
from app.models import AuditEvent, User

ACTIONS = {
    "USER_LOGIN", "USER_REGISTERED", "DOCUMENT_UPLOADED", "DOCUMENT_APPROVED", "DOCUMENT_REJECTED",
    "DOCUMENT_VIEWED", "RESTRICTED_DOCUMENT_DENIED", "SEARCH_EXECUTED", "AI_QUERY_EXECUTED",
    "SCENARIO_CREATED", "SCENARIO_RUN", "SCENARIO_EXPORTED", "MODEL_UPDATED", "MODEL_REVIEWED",
    "USER_ROLE_CHANGED", "WORKSPACE_CREATED", "WORKSPACE_BRIEF_EXPORTED", "ANNOTATION_ADDED",
}


def qhash(text: str) -> str:
    return hashlib.sha256(text.strip().lower().encode()).hexdigest()[:16]


def record(db: Session, request: Request | None, actor: User | None, action: str,
           entity_type: str = "", entity_id: str = "", meta: dict | None = None, commit: bool = True) -> AuditEvent:
    assert action in ACTIONS, f"unknown audit action {action}"
    ip = ua = ""
    if request is not None:
        ip = request.client.host if request.client else ""
        ua = request.headers.get("user-agent", "")[:200]
    ev = AuditEvent(actor_id=actor.id if actor else None, actor_role=role_of(actor), action=action,
                    entity_type=entity_type, entity_id=str(entity_id), ip=ip, user_agent=ua, meta=meta or {})
    db.add(ev)
    if commit:
        db.commit()
    return ev
