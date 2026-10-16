"""Unit tests for GitHub Actions job backend (no network)."""

from __future__ import annotations

import io
import json
import zipfile
from unittest.mock import patch

from sonoplan_api.github_actions_jobs import (
    jobs_backend,
    pending_manifest,
    sync_github_actions_job,
)
from sonoplan_api.models import JobRow


def test_jobs_backend_default_inline(monkeypatch) -> None:
    monkeypatch.delenv("SONOPLAN_JOBS_BACKEND", raising=False)
    monkeypatch.setenv("SONOPLAN_JOBS_INLINE", "1")
    assert jobs_backend() == "inline"


def test_jobs_backend_github_actions(monkeypatch) -> None:
    monkeypatch.setenv("SONOPLAN_JOBS_BACKEND", "github_actions")
    assert jobs_backend() == "github_actions"


def test_pending_manifest_shape() -> None:
    man = pending_manifest(
        job_id="j1",
        revision_id="r1",
        snapshot_hash="a" * 64,
        repo="Lewa2424/sonoplan",
        workflow="run-spps-product-job.yml",
        run_id=42,
    )
    assert man["executionMode"] == "github_actions_pending"
    assert man["mapAvailable"] is False
    assert man["github"]["runId"] == 42
    assert man["github"]["runName"] == "sonoplan-job-j1"


def test_sync_applies_completed_artifact(monkeypatch) -> None:
    monkeypatch.setenv("SONOPLAN_JOBS_BACKEND", "github_actions")
    monkeypatch.setenv("SONOPLAN_GITHUB_TOKEN", "test-token")
    monkeypatch.setenv("SONOPLAN_GITHUB_REPOSITORY", "Lewa2424/sonoplan")

    job = JobRow(
        id="11111111-1111-4111-8111-111111111111",
        project_id="22222222-2222-4222-8222-222222222222",
        revision_id="33333333-3333-4333-8333-333333333333",
        snapshot_hash="b" * 64,
        status="running",
        idempotency_key="idem-ga-1",
        request_fingerprint="c" * 64,
        result_manifest=pending_manifest(
            job_id="11111111-1111-4111-8111-111111111111",
            revision_id="33333333-3333-4333-8333-333333333333",
            snapshot_hash="b" * 64,
            repo="Lewa2424/sonoplan",
            workflow="run-spps-product-job.yml",
            run_id=99,
        ),
    )
    # Avoid FK inserts — patch db.get path by operating on detached row via session merge
    # Use sync with mocked HTTP only; commit against in-memory if fixtures provide project.
    # Simpler: call sync with MagicMock session that tracks the job object.

    class _FakeDb:
        def commit(self) -> None:
            return None

        def refresh(self, obj: JobRow) -> None:
            return None

    manifest = {
        "schemaVersion": "1.0",
        "jobId": job.id,
        "revisionId": job.revision_id,
        "snapshotHash": job.snapshot_hash,
        "mapAvailable": False,
        "punctualReceivers": [
            {
                "receiverId": "r_near",
                "energySumGlobal": 0.07,
                "lpDbGlobal": 82.5,
            }
        ],
        "executionMode": "github_actions_spps",
        "notes": ["live"],
    }
    status_doc = {
        "status": "completed",
        "errorCode": None,
        "errorMessage": None,
    }

    def fake_api(method, path, **kwargs):
        if method == "GET" and path.endswith("/actions/runs/99"):
            return 200, {
                "id": 99,
                "status": "completed",
                "conclusion": "success",
                "html_url": "https://github.com/example/run/99",
            }
        if method == "GET" and path.endswith("/artifacts"):
            return 200, {
                "artifacts": [
                    {
                        "id": 7,
                        "name": f"sonoplan-job-{job.id}",
                        "expired": False,
                    }
                ]
            }
        return 404, {"message": "unexpected " + path}

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("result_manifest.json", json.dumps(manifest))
        zf.writestr("job_status.json", json.dumps(status_doc))
    zip_bytes = buf.getvalue()

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return zip_bytes

    with (
        patch(
            "sonoplan_api.github_actions_jobs._api_request",
            side_effect=fake_api,
        ),
        patch(
            "sonoplan_api.github_actions_jobs.urllib.request.urlopen",
            return_value=_Resp(),
        ),
    ):
        out = sync_github_actions_job(_FakeDb(), job)

    assert out.status == "completed"
    assert out.result_manifest is not None
    assert out.result_manifest["executionMode"] == "github_actions_spps"
    assert out.result_manifest["punctualReceivers"][0]["lpDbGlobal"] == 82.5
    assert out.error_code is None
