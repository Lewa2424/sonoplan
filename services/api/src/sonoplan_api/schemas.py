"""Pydantic request/response models for /api/v1."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = "ok"
    schemaVersion: str = "1.0"


class CapabilitiesResponse(BaseModel):
    stub: bool = Field(True, description="Explicitly marked stub; not a verified SPPS profile")
    engineProfileId: str | None = None
    bandsHz: list[float] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=512)
    ownerId: str | None = None
    accessPolicy: str = "private"


class ProjectSummary(BaseModel):
    id: str
    ownerId: str
    name: str
    accessPolicy: str
    schemaVersion: str
    currentRevisionId: str | None


class ProjectListResponse(BaseModel):
    items: list[ProjectSummary]


class DraftPatch(BaseModel):
    """Full or partial draft body. Model nested under `model` preferred."""

    schemaVersion: str | None = None
    name: str | None = None
    model: dict[str, Any] | None = None
    rooms: list[dict[str, Any]] | None = None
    sources: list[dict[str, Any]] | None = None
    workplaces: list[dict[str, Any]] | None = None
    materials: list[dict[str, Any]] | None = None
    solids: list[dict[str, Any]] | None = None


class DraftResponse(BaseModel):
    projectId: str
    etag: str
    body: dict[str, Any]


class RevisionCreate(BaseModel):
    authorId: str | None = None
    note: str | None = None


class RevisionCreated(BaseModel):
    revisionId: str
    snapshotHash: str
    schemaVersion: str
    projectId: str
    parentId: str | None


class ValidationIssue(BaseModel):
    code: str
    severity: str
    message: str
    path: str | None = None
    entityId: str | None = None


class ValidateResponse(BaseModel):
    revisionId: str
    snapshotHash: str
    ok: bool
    errors: list[ValidationIssue]
    warnings: list[ValidationIssue]
