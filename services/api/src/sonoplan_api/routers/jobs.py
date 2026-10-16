"""Calculation jobs: create (Idempotency-Key), status, cancel."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from sqlalchemy.orm import Session

from sonoplan_api.db import get_db
from sonoplan_api.jobs_service import create_job
from sonoplan_api.models import JobRow, RevisionRow
from sonoplan_api.schemas import JobCreate, JobResponse

router = APIRouter(tags=["jobs"])

TERMINAL = frozenset({"completed", "failed", "cancelled"})


def _iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.isoformat() + "Z"
    return dt.isoformat().replace("+00:00", "Z")


def job_to_response(job: JobRow) -> JobResponse:
    return JobResponse(
        id=job.id,
        projectId=job.project_id,
        revisionId=job.revision_id,
        snapshotHash=job.snapshot_hash,
        status=job.status,
        errorCode=job.error_code,
        errorMessage=job.error_message,
        resultManifest=job.result_manifest,
        cancelRequested=bool(job.cancel_requested),
        createdAt=_iso(job.created_at) or "",
        updatedAt=_iso(job.updated_at) or "",
        startedAt=_iso(job.started_at),
        finishedAt=_iso(job.finished_at),
    )


@router.post("/api/v1/jobs", response_model=JobResponse)
def post_job(
    body: JobCreate,
    response: Response,
    db: Session = Depends(get_db),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> JobResponse:
    if not idempotency_key or not idempotency_key.strip():
        raise HTTPException(
            status_code=400,
            detail="Idempotency-Key header is required",
        )
    key = idempotency_key.strip()
    if len(key) > 128:
        raise HTTPException(status_code=400, detail="Idempotency-Key too long")

    revision = db.get(RevisionRow, body.revisionId)
    if revision is None:
        raise HTTPException(status_code=404, detail="Revision not found")

    snapshot_hash = revision.snapshot_hash
    if body.snapshotHash is not None and body.snapshotHash != snapshot_hash:
        raise HTTPException(
            status_code=409,
            detail="snapshotHash does not match revision",
        )

    try:
        job, created = create_job(
            db,
            revision=revision,
            idempotency_key=key,
            snapshot_hash=snapshot_hash,
        )
    except ValueError as exc:
        if str(exc) == "idempotency_key_reuse_mismatch":
            raise HTTPException(
                status_code=409,
                detail="Idempotency-Key already used with a different request",
            ) from exc
        raise

    response.status_code = 201 if created else 200
    return job_to_response(job)


@router.get("/api/v1/jobs/{job_id}", response_model=JobResponse)
def get_job(job_id: str, db: Session = Depends(get_db)) -> JobResponse:
    job = db.get(JobRow, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job_to_response(job)


@router.post("/api/v1/jobs/{job_id}/cancel", response_model=JobResponse)
def cancel_job(job_id: str, db: Session = Depends(get_db)) -> JobResponse:
    job = db.get(JobRow, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status in TERMINAL:
        # Idempotent cancel on terminal states — return current record.
        return job_to_response(job)

    job.cancel_requested = True
    if job.status in ("created", "queued"):
        job.status = "cancelled"
        job.error_code = "CANCELLED"
        job.error_message = "Job cancelled before start"
        from datetime import timezone

        now = datetime.now(timezone.utc)
        job.finished_at = now
        job.updated_at = now
    else:
        # running: cooperative cancel flag; executor may finish first
        from datetime import timezone

        job.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(job)
    return job_to_response(job)
