"""Celery worker: run calculation jobs via engine/adapter (no fake maps)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from celery import Celery

broker_url = os.environ.get("CELERY_BROKER_URL", "amqp://guest:guest@localhost:5672//")
result_backend = os.environ.get("CELERY_RESULT_BACKEND", "rpc://")

app = Celery("sonoplan_worker", broker=broker_url, backend=result_backend)
app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
)


def _ensure_api_and_adapter_on_path() -> None:
    repo = Path(__file__).resolve().parents[4]
    api_src = repo / "services" / "api" / "src"
    adapter = repo / "engine" / "adapter"
    for path in (api_src, adapter):
        if path.is_dir() and str(path) not in sys.path:
            sys.path.insert(0, str(path))


@app.task(name="sonoplan.run_calculation", bind=True)
def run_calculation(self, job_id: str, revision_id: str) -> dict[str, object]:
    """
    Load job from DB and execute through adapter.

    Must not invent acoustic results. Missing SPPS_BIN / non-Linux → failed with code.
    """
    _ensure_api_and_adapter_on_path()

    from sqlalchemy.orm import sessionmaker

    from sonoplan_api.db import make_engine
    from sonoplan_api.job_execution import execute_job
    import sonoplan_api.models  # noqa: F401 — register ORM

    engine = make_engine()
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = SessionLocal()
    try:
        job = execute_job(db, job_id)
        if job is None:
            return {
                "jobId": job_id,
                "revisionId": revision_id,
                "status": "failed",
                "errorCode": "JOB_NOT_FOUND",
            }
        return {
            "jobId": job.id,
            "revisionId": job.revision_id,
            "snapshotHash": job.snapshot_hash,
            "status": job.status,
            "errorCode": job.error_code,
        }
    finally:
        db.close()
        engine.dispose()
