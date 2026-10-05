import uuid
from datetime import date, datetime

from sqlalchemy import (Boolean, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text,
                        UniqueConstraint, Uuid)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.base import IdMixin, JSONType, SoftDeleteMixin, TimestampMixin

DOCUMENT_STATUSES = ("processing", "pending_review", "approved", "rejected", "failed")
ACCESS_LEVELS = ("public", "restricted", "internal")


class DataSource(IdMixin, TimestampMixin, Base):
    """Provenance record for datasets/indicators/coefficients. `is_demo` marks synthetic data."""
    __tablename__ = "data_sources"
    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    kind: Mapped[str] = mapped_column(String(30), default="statistical")
    organization: Mapped[str] = mapped_column(String(255), default="")
    url: Mapped[str] = mapped_column(String(1000), default="")
    is_demo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    license: Mapped[str] = mapped_column(String(255), default="")


class Document(IdMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "documents"
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    authors: Mapped[list] = mapped_column(JSONType, default=list)
    organization: Mapped[str] = mapped_column(String(255), default="", index=True)
    source_url: Mapped[str] = mapped_column(String(1000), default="")
    document_type: Mapped[str] = mapped_column(String(40), default="policy_report", index=True)
    authority_level: Mapped[str] = mapped_column(String(30), default="institutional")
    language: Mapped[str] = mapped_column(String(10), default="en")
    publication_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    state_code: Mapped[str | None] = mapped_column(String(5), nullable=True, index=True)
    district_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    geography_label: Mapped[str] = mapped_column(String(255), default="India")
    access_level: Mapped[str] = mapped_column(String(20), default="public", index=True)
    status: Mapped[str] = mapped_column(String(20), default="processing", index=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    provenance_note: Mapped[str] = mapped_column(Text, default="")
    extraction_quality: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"), nullable=True)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    versions: Mapped[list["DocumentVersion"]] = relationship(back_populates="document", cascade="all, delete-orphan")
    topics: Mapped[list["Topic"]] = relationship(secondary="document_topics", lazy="selectin")

    __table_args__ = (Index("ix_documents_status_access", "status", "access_level"),)


class DocumentVersion(IdMixin, TimestampMixin, Base):
    __tablename__ = "document_versions"
    document_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)  # SHA-256
    object_uri: Mapped[str] = mapped_column(String(1000), default="")
    extracted_text_uri: Mapped[str] = mapped_column(String(1000), default="")
    page_count: Mapped[int] = mapped_column(Integer, default=1)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True)
    parent_version_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("document_versions.id"), nullable=True)
    document: Mapped[Document] = relationship(back_populates="versions")
    __table_args__ = (UniqueConstraint("document_id", "version_no", name="uq_doc_version"),)


class DocumentChunk(IdMixin, Base):
    """Citation unit. `meta` is an index-time snapshot of citation metadata."""
    __tablename__ = "document_chunks"
    document_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    document_version_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("document_versions.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    page_no: Mapped[int] = mapped_column(Integer, default=1)
    section: Mapped[str] = mapped_column(String(500), default="")
    text: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, default=0)
    embedding: Mapped[list | None] = mapped_column(JSONType, nullable=True)
    embedding_model: Mapped[str] = mapped_column(String(100), default="")
    meta: Mapped[dict] = mapped_column(JSONType, default=dict)
    __table_args__ = (UniqueConstraint("document_version_id", "chunk_index", name="uq_chunk_order"),)


class Topic(IdMixin, Base):
    __tablename__ = "topics"
    name: Mapped[str] = mapped_column(String(150), unique=True, nullable=False)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("topics.id"), nullable=True)


class DocumentTopic(Base):
    __tablename__ = "document_topics"
    document_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True)
    topic_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("topics.id", ondelete="CASCADE"), primary_key=True)


class IngestionJob(IdMixin, TimestampMixin, Base):
    __tablename__ = "ingestion_jobs"
    document_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), default="queued")  # queued|running|done|failed
    stage: Mapped[str] = mapped_column(String(30), default="queued")
    error: Mapped[str] = mapped_column(Text, default="")
    stats: Mapped[dict] = mapped_column(JSONType, default=dict)
    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"), nullable=True)


class Annotation(IdMixin, TimestampMixin, Base):
    __tablename__ = "annotations"
    document_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("document_chunks.id", ondelete="SET NULL"), nullable=True)
    author_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), default="comment")  # comment|flag|verified
    text: Mapped[str] = mapped_column(Text, nullable=False)
