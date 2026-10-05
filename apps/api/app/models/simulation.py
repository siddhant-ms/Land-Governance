import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.base import IdMixin, JSONType, SoftDeleteMixin, TimestampMixin


class SimModel(IdMixin, TimestampMixin, Base):
    __tablename__ = "models"
    key: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[str] = mapped_column(String(20), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    methodology: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="active")  # active|deprecated|draft
    definition: Mapped[dict] = mapped_column(JSONType, default=dict)
    review_status: Mapped[str] = mapped_column(String(30), default="unreviewed")
    review_notes: Mapped[str] = mapped_column(Text, default="")
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    __table_args__ = (UniqueConstraint("key", "version", name="uq_model_version"),)


class Scenario(IdMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "scenarios"
    model_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("models.id"), nullable=False, index=True)
    owner_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False, index=True)
    region_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("regions.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    parameters: Mapped[list["ScenarioParameter"]] = relationship(cascade="all, delete-orphan", lazy="selectin")
    model: Mapped[SimModel] = relationship(lazy="joined")


class ScenarioParameter(IdMixin, Base):
    __tablename__ = "scenario_parameters"
    scenario_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("scenarios.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    __table_args__ = (UniqueConstraint("scenario_id", "name", name="uq_scenario_param"),)


class ScenarioRun(IdMixin, Base):
    __tablename__ = "scenario_runs"
    scenario_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("scenarios.id", ondelete="CASCADE"), nullable=False, index=True)
    model_version: Mapped[str] = mapped_column(String(20), nullable=False)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    output_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    output_json: Mapped[dict] = mapped_column(JSONType, nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
