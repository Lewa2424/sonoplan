"""Execute a calculation job via engine/adapter (no invented acoustic maps)."""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from sonoplan_api.models import JobRow

# Repo-root engine/adapter on PYTHONPATH for monorepo checkout.
_ADAPTER_ROOT = Path(__file__).resolve().parents[4] / "engine" / "adapter"
if _ADAPTER_ROOT.is_dir() and str(_ADAPTER_ROOT) not in sys.path:
    sys.path.insert(0, str(_ADAPTER_ROOT))


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _default_fixture_work_dir() -> Path:
    override = os.environ.get("SONOPLAN_SPPS_WORK_DIR", "").strip()
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[4] / "engine" / "fixtures" / "minimal_room" / "inputs"


def execute_job(db: Session, job_id: str) -> JobRow | None:
    """
    Transition job through running → completed|failed|cancelled.

    Uses adapter env gates + attempt_spps_calculation. On hosts without Linux
    SPPS (Windows MVP), falls back to decoding pinned CI fixture .recp files
    when fixture replay is enabled — never invents dB / heatmaps.
    """
    from sonoplan_adapter.env import check_spps_environment
    from sonoplan_adapter.fixture_replay import (
        attempt_fixture_replay,
        replay_manifest_notes,
    )
    from sonoplan_adapter.job_run import attempt_spps_calculation, build_result_manifest

    job = db.get(JobRow, job_id)
    if job is None:
        return None

    if job.cancel_requested and job.status in ("created", "queued"):
        job.status = "cancelled"
        job.error_code = "CANCELLED"
        job.error_message = "Job cancelled before start"
        job.finished_at = _utcnow()
        job.updated_at = job.finished_at
        db.commit()
        db.refresh(job)
        return job

    if job.status in ("completed", "failed", "cancelled"):
        return job

    job.status = "running"
    job.started_at = _utcnow()
    job.updated_at = job.started_at
    db.commit()

    db.refresh(job)
    if job.cancel_requested:
        job.status = "cancelled"
        job.error_code = "CANCELLED"
        job.error_message = "Job cancelled"
        job.finished_at = _utcnow()
        job.updated_at = job.finished_at
        db.commit()
        db.refresh(job)
        return job

    env = check_spps_environment()
    used_fixture_replay = False
    if env.ok:
        work_dir = _default_fixture_work_dir()
        attempt = attempt_spps_calculation(
            work_dir=work_dir,
            spps_bin=env.spps_bin,
            required_inputs=("config.xml",),
        )
    else:
        # Windows / no SPPS_BIN: decode real CI outputs for MVP path.
        attempt = attempt_fixture_replay()
        used_fixture_replay = attempt.ok
        if not attempt.ok:
            # Prefer the original env gate code when replay is unavailable.
            job.status = "failed"
            job.error_code = env.code or attempt.error_code
            job.error_message = (
                f"{env.message} "
                f"Fixture replay: {attempt.error_message or 'unavailable'}."
            )
            job.result_manifest = build_result_manifest(
                job_id=job.id,
                revision_id=job.revision_id,
                snapshot_hash=job.snapshot_hash,
                attempt=attempt,
            )
            job.finished_at = _utcnow()
            job.updated_at = job.finished_at
            db.commit()
            db.refresh(job)
            return job

    if attempt.ok:
        job.status = "completed"
        job.error_code = None
        job.error_message = None
        job.result_manifest = build_result_manifest(
            job_id=job.id,
            revision_id=job.revision_id,
            snapshot_hash=job.snapshot_hash,
            attempt=attempt,
        )
        if used_fixture_replay:
            notes = list(job.result_manifest.get("notes") or [])
            for n in replay_manifest_notes():
                if n not in notes:
                    notes.insert(0, n)
            job.result_manifest["notes"] = notes
            job.result_manifest["executionMode"] = "fixture_replay"
    else:
        job.status = "failed"
        job.error_code = attempt.error_code
        job.error_message = attempt.error_message
        job.result_manifest = build_result_manifest(
            job_id=job.id,
            revision_id=job.revision_id,
            snapshot_hash=job.snapshot_hash,
            attempt=attempt,
        )

    job.finished_at = _utcnow()
    job.updated_at = job.finished_at
    db.commit()
    db.refresh(job)
    return job
