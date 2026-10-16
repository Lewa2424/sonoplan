"""Decode pinned CI fixture outputs when Linux SPPS cannot run locally.

Used on Windows MVP hosts (no Docker/WSL). Never invents dB: only decodes
real ``Sound level.recp`` from ``engine/fixtures/minimal_room/expected``.
"""

from __future__ import annotations

import os
from pathlib import Path

from .job_run import CalculationAttempt
from .results import decode_spps_workdir

CODE_FIXTURE_REPLAY_UNAVAILABLE = "FIXTURE_REPLAY_UNAVAILABLE"

_REPLAY_NOTE = (
    "executionMode=fixture_replay: levels decoded from pinned CI SPPS outputs "
    "under engine/fixtures/minimal_room/expected (not a local SPPS run of this "
    "project mesh). Surface map still deferred."
)


def fixture_replay_enabled() -> bool:
    """Default ON when unset; disable with SONOPLAN_SPPS_FIXTURE_REPLAY=0."""
    flag = os.environ.get("SONOPLAN_SPPS_FIXTURE_REPLAY", "").strip().lower()
    if flag in ("0", "false", "no", "off"):
        return False
    if flag in ("1", "true", "yes", "on"):
        return True
    return True


def resolve_fixture_replay_dir() -> Path | None:
    override = os.environ.get("SONOPLAN_SPPS_FIXTURE_REPLAY_DIR", "").strip()
    if override:
        path = Path(override)
        return path if path.is_dir() else None
    # engine/adapter/sonoplan_adapter/ → parents[2] = engine/
    default = (
        Path(__file__).resolve().parents[2]
        / "fixtures"
        / "minimal_room"
        / "expected"
    )
    if (default / "Punctual receivers").is_dir():
        return default
    return None


def attempt_fixture_replay(*, work_dir: Path | None = None) -> CalculationAttempt:
    """Complete a calculation from real CI .recp files (decode only)."""
    if not fixture_replay_enabled():
        return CalculationAttempt(
            ok=False,
            error_code=CODE_FIXTURE_REPLAY_UNAVAILABLE,
            error_message=(
                "Fixture replay disabled (SONOPLAN_SPPS_FIXTURE_REPLAY=0). "
                "Linux worker / SPPS_BIN required for a live run."
            ),
            work_dir=str(work_dir) if work_dir else None,
        )

    replay = work_dir or resolve_fixture_replay_dir()
    if replay is None or not replay.is_dir():
        return CalculationAttempt(
            ok=False,
            error_code=CODE_FIXTURE_REPLAY_UNAVAILABLE,
            error_message=(
                "No fixture replay directory "
                "(expected engine/fixtures/minimal_room/expected)."
            ),
            work_dir=str(replay) if replay else None,
        )

    decoded = decode_spps_workdir(replay)
    any_lp = any(
        p.get("lpDbGlobal") is not None for p in decoded.punctual
    )
    if not decoded.ok or not decoded.punctual or not any_lp:
        return CalculationAttempt(
            ok=False,
            error_code=CODE_FIXTURE_REPLAY_UNAVAILABLE,
            error_message=(
                "Fixture replay decode failed or no confirmed lpDb "
                f"(ok={decoded.ok}, punctual={len(decoded.punctual)}, "
                f"errors={decoded.errors[:3]})."
            ),
            work_dir=str(replay),
            artifact_paths=[
                p.get("relativePath", "")
                for p in decoded.punctual
                if p.get("relativePath")
            ],
            failure_reasons=list(decoded.errors),
        )

    artifacts = [
        p["relativePath"]
        for p in decoded.punctual
        if isinstance(p.get("relativePath"), str)
    ]
    return CalculationAttempt(
        ok=True,
        work_dir=str(replay.resolve()),
        artifact_paths=artifacts,
        failure_reasons=[],
        stdout_tail=_REPLAY_NOTE,
    )


def replay_manifest_notes() -> list[str]:
    return [_REPLAY_NOTE]
