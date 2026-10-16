"""Draft ETag helpers."""

from __future__ import annotations

import hashlib
import uuid


def new_etag() -> str:
    return hashlib.sha256(uuid.uuid4().bytes).hexdigest()[:32]


def normalize_etag(value: str | None) -> str | None:
    if value is None:
        return None
    v = value.strip()
    if v.startswith("W/"):
        v = v[2:].strip()
    if len(v) >= 2 and v[0] == '"' and v[-1] == '"':
        v = v[1:-1]
    return v or None
