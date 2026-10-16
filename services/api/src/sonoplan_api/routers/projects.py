from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from sqlalchemy.orm import Session

from sonoplan_api.db import get_db
from sonoplan_api.etag import new_etag, normalize_etag
from sonoplan_api.models import DraftRow, ProjectRow, RevisionRow
from sonoplan_api.schemas import (
    DraftPatch,
    DraftResponse,
    ProjectCreate,
    ProjectListResponse,
    ProjectSummary,
    RevisionCreate,
    RevisionCreated,
)
from sonoplan_api.snapshot import compute_snapshot_hash, default_draft_body, extract_model_from_draft

router = APIRouter(tags=["projects"])


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _project_summary(p: ProjectRow) -> ProjectSummary:
    return ProjectSummary(
        id=p.id,
        ownerId=p.owner_id,
        name=p.name,
        accessPolicy=p.access_policy,
        schemaVersion=p.schema_version,
        currentRevisionId=p.current_revision_id,
    )


@router.get("/api/v1/projects", response_model=ProjectListResponse)
def list_projects(db: Session = Depends(get_db)) -> ProjectListResponse:
    rows = db.query(ProjectRow).order_by(ProjectRow.created_at.desc()).all()
    return ProjectListResponse(items=[_project_summary(p) for p in rows])


@router.post("/api/v1/projects", response_model=ProjectSummary, status_code=201)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)) -> ProjectSummary:
    owner_id = payload.ownerId or str(uuid.uuid4())
    project = ProjectRow(
        id=str(uuid.uuid4()),
        owner_id=owner_id,
        name=payload.name,
        access_policy=payload.accessPolicy,
        schema_version="1.0",
        current_revision_id=None,
        created_at=_utcnow(),
        updated_at=_utcnow(),
    )
    etag = new_etag()
    draft = DraftRow(
        project_id=project.id,
        etag=etag,
        body=default_draft_body(payload.name),
        updated_at=_utcnow(),
    )
    db.add(project)
    db.add(draft)
    db.commit()
    db.refresh(project)
    return _project_summary(project)


@router.get("/api/v1/projects/{project_id}/draft", response_model=DraftResponse)
def get_draft(project_id: str, response: Response, db: Session = Depends(get_db)) -> DraftResponse:
    draft = db.get(DraftRow, project_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="Draft not found")
    response.headers["ETag"] = f'"{draft.etag}"'
    return DraftResponse(projectId=project_id, etag=draft.etag, body=draft.body)


def _merge_draft(body: dict[str, Any], patch: DraftPatch) -> dict[str, Any]:
    merged = dict(body)
    data = patch.model_dump(exclude_unset=True)
    if "name" in data and data["name"] is not None:
        merged["name"] = data["name"]
    if "schemaVersion" in data and data["schemaVersion"] is not None:
        merged["schemaVersion"] = data["schemaVersion"]

    model = dict(merged.get("model") or {})
    if "model" in data and data["model"] is not None:
        model.update(data["model"])
    for key in ("rooms", "sources", "workplaces", "materials", "solids"):
        if key in data and data[key] is not None:
            model[key] = data[key]
    if "schemaVersion" not in model:
        model["schemaVersion"] = merged.get("schemaVersion", "1.0")
    merged["model"] = model
    return merged


@router.patch("/api/v1/projects/{project_id}/draft", response_model=DraftResponse)
def patch_draft(
    project_id: str,
    payload: DraftPatch,
    response: Response,
    db: Session = Depends(get_db),
    if_match: str | None = Header(default=None, alias="If-Match"),
) -> DraftResponse:
    draft = db.get(DraftRow, project_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="Draft not found")

    incoming = normalize_etag(if_match)
    if incoming is None:
        # Optimistic concurrency required — no silent overwrite.
        raise HTTPException(status_code=428, detail="If-Match header required")
    if incoming != draft.etag:
        raise HTTPException(status_code=412, detail="ETag mismatch")

    draft.body = _merge_draft(draft.body, payload)
    draft.etag = new_etag()
    draft.updated_at = _utcnow()
    project = db.get(ProjectRow, project_id)
    if project is not None and isinstance(draft.body.get("name"), str):
        project.name = draft.body["name"]
        project.updated_at = _utcnow()
    db.commit()
    db.refresh(draft)
    response.headers["ETag"] = f'"{draft.etag}"'
    return DraftResponse(projectId=project_id, etag=draft.etag, body=draft.body)


@router.post(
    "/api/v1/projects/{project_id}/revisions",
    response_model=RevisionCreated,
    status_code=201,
    tags=["revisions"],
)
def create_revision(
    project_id: str,
    payload: RevisionCreate,
    db: Session = Depends(get_db),
) -> RevisionCreated:
    project = db.get(ProjectRow, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    draft = db.get(DraftRow, project_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="Draft not found")

    model = extract_model_from_draft(draft.body)
    snapshot_hash = compute_snapshot_hash(model)
    revision = RevisionRow(
        id=str(uuid.uuid4()),
        project_id=project_id,
        parent_id=project.current_revision_id,
        schema_version="1.0",
        author_id=payload.authorId or project.owner_id,
        created_at=_utcnow(),
        snapshot_hash=snapshot_hash,
        snapshot=model,
        note=payload.note,
    )
    db.add(revision)
    project.current_revision_id = revision.id
    project.updated_at = _utcnow()
    db.commit()
    db.refresh(revision)
    return RevisionCreated(
        revisionId=revision.id,
        snapshotHash=revision.snapshot_hash,
        schemaVersion=revision.schema_version,
        projectId=project_id,
        parentId=revision.parent_id,
    )
