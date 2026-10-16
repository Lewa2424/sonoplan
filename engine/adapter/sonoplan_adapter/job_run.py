"""High-level calculation attempt for worker / CI.

Does not invent Lp/Lw maps. Completes only when SPPS exits with valid outputs.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .contracts import SppsRunRequest
from .env import (
    CODE_FIXTURE_INPUTS_MISSING,
    CODE_SPPS_RUN_FAILED,
    check_spps_environment,
    fixture_inputs_ready,
)
from .runner import run_spps


@dataclass
class CalculationAttempt:
    """Outcome of one adapter→SPPS attempt (not a published ResultManifest alone)."""

    ok: bool
    error_code: str | None = None
    error_message: str | None = None
    spps_bin: str | None = None
    work_dir: str | None = None
    exit_code: int | None = None
    duration_s: float | None = None
    failure_reasons: list[str] = field(default_factory=list)
    output_checks: list[dict[str, Any]] = field(default_factory=list)
    artifact_paths: list[str] = field(default_factory=list)
    stdout_tail: str | None = None
    stderr_tail: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _tail(text: str, limit: int = 4000) -> str:
    if len(text) <= limit:
        return text
    return text[-limit:]


def attempt_spps_calculation(
    *,
    work_dir: Path,
    config_xml_name: str = "config.xml",
    spps_bin: str | None = None,
    required_inputs: tuple[str, ...] = ("config.xml",),
) -> CalculationAttempt:
    env = check_spps_environment(spps_bin=spps_bin)
    if not env.ok:
        return CalculationAttempt(
            ok=False,
            error_code=env.code,
            error_message=env.message,
            spps_bin=env.spps_bin,
            work_dir=str(work_dir),
        )

    work = work_dir.resolve()
    if not work.is_dir():
        return CalculationAttempt(
            ok=False,
            error_code=CODE_FIXTURE_INPUTS_MISSING,
            error_message=f"work_dir missing: {work}",
            spps_bin=env.spps_bin,
            work_dir=str(work),
        )

    if not fixture_inputs_ready(work, required_inputs):
        missing = [n for n in required_inputs if not (work / n).is_file()]
        return CalculationAttempt(
            ok=False,
            error_code=CODE_FIXTURE_INPUTS_MISSING,
            error_message=(
                "SPPS fixture inputs are not ready "
                f"(missing: {', '.join(missing)}). "
                "Do not invent mesh/config; fill engine/fixtures after first real prep."
            ),
            spps_bin=env.spps_bin,
            work_dir=str(work),
        )

    result = run_spps(
        SppsRunRequest(
            work_dir=str(work),
            config_xml_name=config_xml_name,
            spps_executable=env.spps_bin or "spps",
        )
    )
    stdout_tail = _tail(result.stdout or "")
    stderr_tail = _tail(result.stderr or "")
    if not result.ok:
        reasons = list(result.failure_reasons)
        return CalculationAttempt(
            ok=False,
            error_code=CODE_SPPS_RUN_FAILED,
            error_message="; ".join(reasons) or "SPPS run failed",
            spps_bin=env.spps_bin,
            work_dir=result.work_dir,
            exit_code=result.exit_code,
            duration_s=result.duration_s,
            failure_reasons=reasons,
            output_checks=list(result.output_checks),
            stdout_tail=stdout_tail or None,
            stderr_tail=stderr_tail or None,
        )

    artifacts = [
        c["path"]
        for c in result.output_checks
        if c.get("exists") and c.get("ok")
    ]
    return CalculationAttempt(
        ok=True,
        spps_bin=env.spps_bin,
        work_dir=result.work_dir,
        exit_code=result.exit_code,
        duration_s=result.duration_s,
        failure_reasons=[],
        output_checks=list(result.output_checks),
        artifact_paths=artifacts,
        stdout_tail=stdout_tail or None,
        stderr_tail=stderr_tail or None,
    )


def build_result_manifest(
    *,
    job_id: str,
    revision_id: str,
    snapshot_hash: str,
    attempt: CalculationAttempt,
) -> dict[str, Any]:
    """ResultManifest-shaped JSON. No invented dB fields."""
    map_available = bool(attempt.ok and attempt.artifact_paths)
    return {
        "schemaVersion": "1.0",
        "jobId": job_id,
        "revisionId": revision_id,
        "snapshotHash": snapshot_hash,
        "quantity": None,
        "unit": None,
        "grid": None,
        "masks": None,
        "artifactPaths": list(attempt.artifact_paths),
        "mapAvailable": map_available,
        "mapDeferredReason": None
        if map_available
        else "Карта позже: нет декодированных акустических выборок (не подставляем дБ).",
        "notes": [
            "Базовый SPPS не заявляет дифракцию/интерференцию/моды как рассчитанные.",
            "Lw ≠ Lp; значения дБ публикуются только после проверенного декодера выходов.",
        ],
        "attempt": attempt.to_dict(),
    }


def write_attempt_report(path: Path, attempt: CalculationAttempt) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(attempt.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
