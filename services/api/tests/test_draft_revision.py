"""API integration: draft ETag conflict + create revision (SQLite test DB only)."""

from __future__ import annotations


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


def test_create_list_project(client) -> None:
    r = client.post("/api/v1/projects", json={"name": "Цех А"})
    assert r.status_code == 201
    project = r.json()
    assert project["name"] == "Цех А"
    assert project["schemaVersion"] == "1.1"
    assert project["currentRevisionId"] is None
    draft = client.get(f"/api/v1/projects/{project['id']}/draft").json()
    assert draft["body"]["model"]["schemaVersion"] == "1.1"

    listed = client.get("/api/v1/projects")
    assert listed.status_code == 200
    assert any(p["id"] == project["id"] for p in listed.json()["items"])


def test_draft_etag_conflict(client) -> None:
    created = client.post("/api/v1/projects", json={"name": "ETag test"}).json()
    project_id = created["id"]

    get1 = client.get(f"/api/v1/projects/{project_id}/draft")
    assert get1.status_code == 200
    etag = get1.headers["etag"].strip('"')
    assert get1.json()["etag"] == etag

    ok = client.patch(
        f"/api/v1/projects/{project_id}/draft",
        headers={"If-Match": etag},
        json={"name": "ETag test v2", "model": _rect_model()},
    )
    assert ok.status_code == 200
    new_etag = ok.json()["etag"]
    assert new_etag != etag

    # Stale If-Match → 412 Precondition Failed (optimistic lock)
    stale = client.patch(
        f"/api/v1/projects/{project_id}/draft",
        headers={"If-Match": etag},
        json={"name": "should fail"},
    )
    assert stale.status_code in (409, 412)

    missing = client.patch(
        f"/api/v1/projects/{project_id}/draft",
        json={"name": "no if-match"},
    )
    assert missing.status_code in (412, 428)


def test_create_revision_returns_hash(client) -> None:
    created = client.post("/api/v1/projects", json={"name": "Rev test"}).json()
    project_id = created["id"]
    draft = client.get(f"/api/v1/projects/{project_id}/draft").json()
    etag = draft["etag"]

    patched = client.patch(
        f"/api/v1/projects/{project_id}/draft",
        headers={"If-Match": etag},
        json={"model": _rect_model()},
    )
    assert patched.status_code == 200

    rev = client.post(f"/api/v1/projects/{project_id}/revisions", json={})
    assert rev.status_code == 201
    body = rev.json()
    assert body["revisionId"]
    assert len(body["snapshotHash"]) == 64
    assert body["projectId"] == project_id

    project = client.get("/api/v1/projects").json()["items"]
    match = next(p for p in project if p["id"] == project_id)
    assert match["currentRevisionId"] == body["revisionId"]

    validated = client.post(f"/api/v1/revisions/{body['revisionId']}/validate")
    assert validated.status_code == 200
    v = validated.json()
    assert v["ok"] is True
    assert v["errors"] == []
    assert v["snapshotHash"] == body["snapshotHash"]


def _surface_model(ceiling: str | None) -> dict:
    model = _rect_model()
    model["schemaVersion"] = "1.1"
    room = model["rooms"][0]
    mat = room.pop("materialVersionId")
    room["surfaceMaterials"] = {"floor": mat, "walls": mat, "ceiling": ceiling}
    return model


def _revision_of(client, model: dict) -> dict:
    project_id = client.post("/api/v1/projects", json={"name": "Surfaces"}).json()["id"]
    etag = client.get(f"/api/v1/projects/{project_id}/draft").json()["etag"]
    client.patch(
        f"/api/v1/projects/{project_id}/draft",
        headers={"If-Match": etag},
        json={"model": model},
    )
    rev = client.post(f"/api/v1/projects/{project_id}/revisions", json={}).json()
    summary = next(
        p for p in client.get("/api/v1/projects").json()["items"] if p["id"] == project_id
    )
    return {"rev": rev, "project": summary}


def test_schema_11_revision_validates_each_surface_material(client) -> None:
    ok = _revision_of(client, _surface_model("22222222-2222-4222-8222-222222222222"))
    assert ok["rev"]["schemaVersion"] == "1.1"
    assert ok["project"]["schemaVersion"] == "1.1"
    v = client.post(f"/api/v1/revisions/{ok['rev']['revisionId']}/validate").json()
    assert v["ok"] is True

    bad = _revision_of(client, _surface_model(None))
    v = client.post(f"/api/v1/revisions/{bad['rev']['revisionId']}/validate").json()
    assert v["ok"] is False
    missing = [e for e in v["errors"] if e["code"] == "room_surface_material_missing"]
    assert [e["path"] for e in missing] == [
        "rooms/11111111-1111-4111-8111-111111111111/surfaceMaterials/ceiling"
    ]


def test_legacy_10_draft_keeps_its_version_on_revision(client) -> None:
    legacy = _revision_of(client, _rect_model())
    assert legacy["rev"]["schemaVersion"] == "1.0"
    assert legacy["project"]["schemaVersion"] == "1.0"
    v = client.post(f"/api/v1/revisions/{legacy['rev']['revisionId']}/validate").json()
    assert v["ok"] is True


def test_validate_reports_contour_and_spectrum_errors(client) -> None:
    created = client.post("/api/v1/projects", json={"name": "Bad model"}).json()
    project_id = created["id"]
    etag = client.get(f"/api/v1/projects/{project_id}/draft").json()["etag"]

    bad = _rect_model()
    # open contour + empty spectrum
    bad["rooms"][0]["floorContour"] = [
        {"x": 0, "y": 0},
        {"x": 10, "y": 0},
        {"x": 10, "y": 6},
        {"x": 0, "y": 6},
    ]
    bad["sources"][0]["powerSpectrumLw"] = []
    bad["materials"][0]["estimated"] = True

    client.patch(
        f"/api/v1/projects/{project_id}/draft",
        headers={"If-Match": etag},
        json={"model": bad},
    )
    rev_id = client.post(f"/api/v1/projects/{project_id}/revisions", json={}).json()[
        "revisionId"
    ]
    v = client.post(f"/api/v1/revisions/{rev_id}/validate").json()
    assert v["ok"] is False
    codes = {e["code"] for e in v["errors"]}
    assert "contour_not_closed" in codes
    assert "source_spectrum_missing" in codes
    assert any(w["code"] == "material_estimated" for w in v["warnings"])
