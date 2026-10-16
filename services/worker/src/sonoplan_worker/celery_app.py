"""Celery app stub. Adapter/SPPS will be wired after STG-01."""

from __future__ import annotations

import os

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


@app.task(name="sonoplan.run_calculation")
def run_calculation(job_id: str, revision_id: str) -> dict[str, object]:
    """
    Placeholder task.

    Will call engine/adapter → SPPS later. Must not invent acoustic results.
    """
    return {
        "stub": True,
        "jobId": job_id,
        "revisionId": revision_id,
        "status": "not_implemented",
        "note": "Adapter/SPPS not connected; no acoustic output produced",
    }
