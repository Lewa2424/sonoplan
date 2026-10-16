"""SQLAlchemy ORM models for projects, drafts, revisions."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from sonoplan_api.db import Base


def _uuid_str() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ProjectRow(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    owner_id: Mapped[str] = mapped_column(String(36), nullable=False)
    name: Mapped[str] = mapped_column(String(512), nullable=False)
    access_policy: Mapped[str] = mapped_column(String(64), nullable=False, default="private")
    schema_version: Mapped[str] = mapped_column(String(16), nullable=False, default="1.0")
    current_revision_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    draft: Mapped[DraftRow | None] = relationship(
        back_populates="project",
        uselist=False,
        cascade="all, delete-orphan",
    )
    revisions: Mapped[list[RevisionRow]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )


class DraftRow(Base):
    __tablename__ = "drafts"

    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True
    )
    etag: Mapped[str] = mapped_column(String(64), nullable=False)
    body: Mapped[dict] = mapped_column(JSON, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    project: Mapped[ProjectRow] = relationship(back_populates="draft")


class RevisionRow(Base):
    __tablename__ = "revisions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    parent_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    schema_version: Mapped[str] = mapped_column(String(16), nullable=False, default="1.0")
    author_id: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    snapshot_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    # Immutable model snapshot JSON (rooms/sources/…); never patched in place.
    snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    project: Mapped[ProjectRow] = relationship(back_populates="revisions")
