"""API: job idempotency + state transitions (SQLite test DB only)."""

from __future__ import annotations

import uuid


def _rect_model() -> dict:
    return {
        "schemaVersion": "1.0",
        "rooms": [
            {
                "id": "11111111-1111-4111-8111-111111111111",
                "floorContour": [
                    {"x": 0, "y": 0},
                    {"x": 10, "y": 0},
                    {"x": 10, "y": 6},
                    {"x": 0, "y": 6},
                    {"x": 0, "y": 0},
                ],
                "heightM": {"value": 4, "unit": "m"},
                "materialVersionId": "22222222-2222-4222-8222-222222222222",
            }
        ],
        "sources": [
            {
                "id": "33333333-3333-4333-8333-333333333333",
                "name": "Fan",
                "position": {"x": 2, "y": 2, "z": 1.2},
                "powerSpectrumLw": [
                    {"bandHz": 500, "level": {"value": 85, "unit": "dB"}},
                    {"bandHz": 1000, "level": {"value": 82, "unit": "dB"}},
                ],
                "directivityId": None,
                "weight": None,
                "weightNullReason": "not_applicable",
            }
        ],
        "workplaces": [
            {
                "id": "44444444-4444-4444-8444-444444444444",
                "name": "WP-1",
                "kind": "point",
                "position": {"x": 8, "y": 4, "z": 0},
                "receiverHeightM": {"value": 1.5, "unit": "m"},
                "scheduleId": None,
            }
        ],
        "materials": [
            {
                "id": "22222222-2222-4222-8222-222222222222",
                "catalogKey": "concrete",
                "name": "Бетон",
                "version": "1",
                "absorptionByBand": [{"bandHz": 500, "alpha": 0.02}],
                "estimated": False,
            }
        ],
        "solids": [],
    }


def _create_revision(client) -> dict:
    project = client.post("/api/v1/projects", json={"name": "Jobs test"}).json()
    project_id = project["id"]
    etag = client.get(f"/api/v1/projects/{project_id}/draft").json()["etag"]
    client.patch(
        f"/api/v1/projects/{project_id}/draft",
        headers={"If-Match": etag},
        json={"model": _rect_model()},
    )
    return client.post(f"/api/v1/projects/{project_id}/revisions", json={}).json()


def test_create_job_requires_idempotency_key(client) -> None:
    rev = _create_revision(client)
    r = client.post("/api/v1/jobs", json={"revisionId": rev["revisionId"]})
    assert r.status_code == 400


def test_job_idempotency_returns_same_job(client) -> None:
    rev = _create_revision(client)
    key = f"idem-{uuid.uuid4()}"
    headers = {"Idempotency-Key": key}
    body = {
        "revisionId": rev["revisionId"],
        "snapshotHash": rev["snapshotHash"],
    }
    first = client.post("/api/v1/jobs", headers=headers, json=body)
    assert first.status_code == 201
    job1 = first.json()
    assert job1["revisionId"] == rev["revisionId"]
    assert job1["snapshotHash"] == rev["snapshotHash"]
    assert job1["status"] in ("failed", "completed", "cancelled", "running", "queued")
    # On Windows / without SPPS_BIN inline executor fails with a clear code.
    if job1["status"] == "failed":
        assert job1["errorCode"] in (
            "SPPS_NOT_LINUX",
            "SPPS_BIN_MISSING",
            "SPPS_EXECUTABLE_NOT_FOUND",
            "SPPS_NOT_ELF",
            "FIXTURE_INPUTS_MISSING",
            "SPPS_RUN_FAILED",
        )
        assert job1["errorMessage"]
        # Must not publish a fake heatmap.
        manifest = job1.get("resultManifest")
        if manifest is not None:
            assert manifest.get("mapAvailable") is False
            assert manifest.get("quantity") is None

    second = client.post("/api/v1/jobs", headers=headers, json=body)
    assert second.status_code == 200
    job2 = second.json()
    assert job2["id"] == job1["id"]
    assert job2["status"] == job1["status"]


def test_idempotency_key_mismatch_conflict(client) -> None:
    rev_a = _create_revision(client)
    rev_b = _create_revision(client)
    key = f"reuse-{uuid.uuid4()}"
    first = client.post(
        "/api/v1/jobs",
        headers={"Idempotency-Key": key},
        json={"revisionId": rev_a["revisionId"]},
    )
    assert first.status_code == 201
    conflict = client.post(
        "/api/v1/jobs",
        headers={"Idempotency-Key": key},
        json={"revisionId": rev_b["revisionId"]},
    )
    assert conflict.status_code == 409


def test_get_job_and_snapshot_hash_mismatch(client) -> None:
    rev = _create_revision(client)
    bad = client.post(
        "/api/v1/jobs",
        headers={"Idempotency-Key": f"badhash-{uuid.uuid4()}"},
        json={
            "revisionId": rev["revisionId"],
            "snapshotHash": "0" * 64,
        },
    )
    assert bad.status_code == 409

    created = client.post(
        "/api/v1/jobs",
        headers={"Idempotency-Key": f"ok-{uuid.uuid4()}"},
        json={"revisionId": rev["revisionId"]},
    ).json()
    got = client.get(f"/api/v1/jobs/{created['id']}")
    assert got.status_code == 200
    assert got.json()["id"] == created["id"]

    missing = client.get("/api/v1/jobs/00000000-0000-4000-8000-000000000000")
    assert missing.status_code == 404


def test_cancel_terminal_is_idempotent(client) -> None:
    rev = _create_revision(client)
    job = client.post(
        "/api/v1/jobs",
        headers={"Idempotency-Key": f"cancel-{uuid.uuid4()}"},
        json={"revisionId": rev["revisionId"]},
    ).json()
    # Inline executor usually finishes immediately → terminal.
    assert job["status"] in ("failed", "completed", "cancelled")
    cancelled = client.post(f"/api/v1/jobs/{job['id']}/cancel")
    assert cancelled.status_code == 200
    assert cancelled.json()["id"] == job["id"]
    assert cancelled.json()["status"] == job["status"]
