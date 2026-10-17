def test_health_ok(client) -> None:
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["schemaVersion"] == "1.1"


def test_capabilities_is_stub(client) -> None:
    r = client.get("/api/v1/capabilities")
    assert r.status_code == 200
    body = r.json()
    assert body["stub"] is True
    assert body["engineProfileId"] is None
    assert body["bandsHz"] == []
