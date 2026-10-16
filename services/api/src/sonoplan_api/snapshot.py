"""Canonical JSON + snapshotHash (must match packages/domain semantics)."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def sort_keys_deep(value: Any) -> Any:
    if value is None or not isinstance(value, (dict, list)):
        return value
    if isinstance(value, list):
        return [sort_keys_deep(v) for v in value]
    return {k: sort_keys_deep(value[k]) for k in sorted(value.keys())}


def canonical_json(value: Any) -> str:
    return json.dumps(sort_keys_deep(value), ensure_ascii=False, separators=(",", ":"))


def snapshot_hash_payload(snapshot: dict[str, Any]) -> dict[str, Any]:
    return {
        "schemaVersion": snapshot.get("schemaVersion"),
        "rooms": snapshot.get("rooms", []),
        "sources": snapshot.get("sources", []),
        "workplaces": snapshot.get("workplaces", []),
        "materials": snapshot.get("materials", []),
        "solids": snapshot.get("solids", []),
    }


def compute_snapshot_hash(snapshot: dict[str, Any]) -> str:
    payload = snapshot_hash_payload(snapshot)
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def empty_model_snapshot() -> dict[str, Any]:
    return {
        "schemaVersion": "1.0",
        "rooms": [],
        "sources": [],
        "workplaces": [],
        "materials": [],
        "solids": [],
    }


def default_draft_body(name: str) -> dict[str, Any]:
    return {
        "schemaVersion": "1.0",
        "name": name,
        "model": empty_model_snapshot(),
    }


def extract_model_from_draft(body: dict[str, Any]) -> dict[str, Any]:
    model = body.get("model")
    if isinstance(model, dict):
        return {
            "schemaVersion": model.get("schemaVersion", body.get("schemaVersion", "1.0")),
            "rooms": model.get("rooms", []),
            "sources": model.get("sources", []),
            "workplaces": model.get("workplaces", []),
            "materials": model.get("materials", []),
            "solids": model.get("solids", []),
        }
    # Allow flat draft for convenience
    return {
        "schemaVersion": body.get("schemaVersion", "1.0"),
        "rooms": body.get("rooms", []),
        "sources": body.get("sources", []),
        "workplaces": body.get("workplaces", []),
        "materials": body.get("materials", []),
        "solids": body.get("solids", []),
    }
