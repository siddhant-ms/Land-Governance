import uuid

from sqlalchemy import ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.base import IdMixin, JSONType, SoftDeleteMixin, TimestampMixin

ITEM_TYPES = ("document", "citation", "search", "answer", "map", "scenario", "note")


class Workspace(IdMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "workspaces"
    owner_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    research_question: Mapped[str] = mapped_column(Text, default="")
    items: Mapped[list["WorkspaceItem"]] = relationship(cascade="all, delete-orphan", order_by="WorkspaceItem.created_at", lazy="selectin")


class WorkspaceItem(IdMixin, TimestampMixin, Base):
    __tablename__ = "workspace_items"
    workspace_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    item_type: Mapped[str] = mapped_column(String(20), nullable=False)
    ref_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    title: Mapped[str] = mapped_column(String(500), default="")
    payload: Mapped[dict] = mapped_column(JSONType, default=dict)
    note: Mapped[str] = mapped_column(Text, default="")
    tags: Mapped[list] = mapped_column(JSONType, default=list)
