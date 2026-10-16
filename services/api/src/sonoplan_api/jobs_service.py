"""Job create / enqueue / cancel helpers."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from sonoplan_api.github_actions_jobs import (
    enqueue_github_actions_job,
    jobs_backend,
    sync_github_actions_job,
)
from sonoplan_api.job_execution import execute_job
from sonoplan_api.models import JobRow, RevisionRow


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def jobs_inline() -> bool:
    """Default inline for local/tests; set SONOPLAN_JOBS_BACKEND=github_actions to offload."""
    return jobs_backend() == "inline"


def request_fingerprint(revision_id: str, snapshot_hash: str) -> str:
    payload = json.dumps(
        {"revisionId": revision_id, "snapshotHash": snapshot_hash},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def enqueue_job(db: Session, job: JobRow) -> JobRow:
    backend = jobs_backend()

    if backend == "github_actions":
        return enqueue_github_actions_job(db, job)

    job.status = "queued"
    job.updated_at = _utcnow()
    db.commit()
    db.refresh(job)

    if backend == "inline":
        executed = execute_job(db, job.id)
        return executed if executed is not None else job

    # celery
    try:
        from sonoplan_worker.celery_app import run_calculation

        run_calculation.delay(job.id, job.revision_id)
    except Exception as exc:  # noqa: BLE001 — broker missing → fail job clearly
        job.status = "failed"
        job.error_code = "ENQUEUE_FAILED"
        job.error_message = f"Could not enqueue Celery task: {exc}"
        job.finished_at = _utcnow()
        job.updated_at = job.finished_at
        db.commit()
        db.refresh(job)
    return job


def refresh_job(db: Session, job: JobRow) -> JobRow:
    """Sync remote worker progress (GitHub Actions) on read."""
    if jobs_backend() == "github_actions" and job.status in (
        "queued",
        "running",
    ):
        return sync_github_actions_job(db, job)
    return job


def create_job(
    db: Session,
    *,
    revision: RevisionRow,
    idempotency_key: str,
    snapshot_hash: str,
) -> tuple[JobRow, bool]:
    """
    Create or return existing job for Idempotency-Key.

    Returns (job, created).
    """
    existing = db.scalars(
        select(JobRow).where(JobRow.idempotency_key == idempotency_key)
    ).one_or_none()
    fp = request_fingerprint(revision.id, snapshot_hash)
    if existing is not None:
        if existing.request_fingerprint != fp:
            raise ValueError("idempotency_key_reuse_mismatch")
        return existing, False

    job = JobRow(
        project_id=revision.project_id,
        revision_id=revision.id,
        snapshot_hash=snapshot_hash,
        status="created",
        idempotency_key=idempotency_key,
        request_fingerprint=fp,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    job = enqueue_job(db, job)
    return job, True
