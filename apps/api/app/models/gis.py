import uuid

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base import IdMixin, JSONType, TimestampMixin


class Region(IdMixin, TimestampMixin, Base):
    __tablename__ = "regions"
    level: Mapped[str] = mapped_column(String(10), nullable=False, index=True)  # country|state|district
    state_code: Mapped[str] = mapped_column(String(5), nullable=False, index=True)
    district_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("regions.id"), nullable=True)
    geometry: Mapped[dict] = mapped_column(JSONType, nullable=False)  # GeoJSON geometry (EPSG:4326)
    centroid_lon: Mapped[float] = mapped_column(Float, default=0.0)
    centroid_lat: Mapped[float] = mapped_column(Float, default=0.0)
    is_schematic: Mapped[bool] = mapped_column(Boolean, default=True)
    __table_args__ = (UniqueConstraint("state_code", "district_code", name="uq_region_codes"),)


class Indicator(IdMixin, TimestampMixin, Base):
    __tablename__ = "indicators"
    key: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    unit: Mapped[str] = mapped_column(String(50), default="")
    category: Mapped[str] = mapped_column(String(50), default="governance")  # land_use|climate|governance
    description: Mapped[str] = mapped_column(Text, default="")
    source_definition: Mapped[str] = mapped_column(Text, default="")
    data_source_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("data_sources.id"), nullable=True)
    access_level: Mapped[str] = mapped_column(String(20), default="public")
    higher_is_better: Mapped[bool] = mapped_column(Boolean, default=True)
    legend_min: Mapped[float] = mapped_column(Float, default=0.0)
    legend_max: Mapped[float] = mapped_column(Float, default=100.0)


class Observation(IdMixin, Base):
    __tablename__ = "observations"
    indicator_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("indicators.id", ondelete="CASCADE"), nullable=False, index=True)
    region_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("regions.id", ondelete="CASCADE"), nullable=False, index=True)
    period: Mapped[int] = mapped_column(Integer, nullable=False)  # calendar year
    value: Mapped[float] = mapped_column(Float, nullable=False)
    source_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("data_sources.id"), nullable=True)
    __table_args__ = (UniqueConstraint("indicator_id", "region_id", "period", name="uq_observation"),)
