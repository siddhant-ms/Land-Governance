import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base import IdMixin, JSONType, utcnow


class AuditEvent(IdMixin, Base):
    """Append-only. No update/delete paths exist in application code."""
    __tablename__ = "audit_events"
    actor_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"), nullable=True, index=True)
    actor_role: Mapped[str] = mapped_column(String(30), default="public")
    action: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(40), default="")
    entity_id: Mapped[str] = mapped_column(String(100), default="")
    ip: Mapped[str] = mapped_column(String(64), default="")
    user_agent: Mapped[str] = mapped_column(String(200), default="")
    meta: Mapped[dict] = mapped_column(JSONType, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)
    __table_args__ = (Index("ix_audit_entity", "entity_type", "entity_id"),)
