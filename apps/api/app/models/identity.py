import uuid

from sqlalchemy import ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.base import IdMixin, TimestampMixin


class Organization(IdMixin, TimestampMixin, Base):
    __tablename__ = "organizations"
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    type: Mapped[str] = mapped_column(String(50), default="other")  # government|academic|ngo|other
    verified_status: Mapped[str] = mapped_column(String(20), default="unverified")


class Role(IdMixin, Base):
    __tablename__ = "roles"
    name: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(String(255), default="")


class User(IdMixin, TimestampMixin, Base):
    __tablename__ = "users"
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    org_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("organizations.id"), nullable=True)
    role_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("roles.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), default="active")  # active|disabled
    role: Mapped[Role] = relationship(lazy="joined")
    organization: Mapped[Organization | None] = relationship(lazy="joined")
