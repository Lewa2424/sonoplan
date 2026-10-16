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
from .results import decode_spps_workdir
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


def _tail(text: str, limit: int = 80000) -> str:
    """Keep a large tail so SPPS -v load lines remain visible in CI artifacts."""
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
            verbose=True,
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
    decoded: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """ResultManifest-shaped JSON. No invented dB / heatmap fields.

    When ``decoded`` is provided (post-SPPS GABE/.recp decode), punctual
    summaries are attached. Surface map stays unavailable until .csbin decode.
    Lp is published only when energy_sum > 0 (zero energy ≠ 0 dB).
    """
    work = Path(attempt.work_dir) if attempt.work_dir else None
    if decoded is None and attempt.ok and work is not None and work.is_dir():
        decoded = decode_spps_workdir(work).to_dict()

    punctual = list((decoded or {}).get("punctual") or [])
    any_lp = any(p.get("lpDbGlobal") is not None for p in punctual)
    decode_ok = bool((decoded or {}).get("ok"))
    surface = (decoded or {}).get("surface") or None
    grid = None
    map_available = False
    map_fill_ratio = 0.0
    # Sparse/diagonal blotches (e.g. coplanar sources) must not ship as a "map".
    _MIN_MAP_FILL = 0.45
    if isinstance(surface, dict):
        cand = surface.get("grid")
        if isinstance(cand, dict) and cand.get("lpDb"):
            lp_cells = list(cand.get("lpDb") or [])
            filled = sum(1 for v in lp_cells if v is not None)
            map_fill_ratio = (filled / len(lp_cells)) if lp_cells else 0.0
            if filled > 0 and map_fill_ratio >= _MIN_MAP_FILL:
                grid = cand
                map_available = True

    # Surface heatmap only from decoded .csbin — never invented from punctual.
    if map_available:
        map_deferred = None
    elif attempt.ok and decode_ok and punctual and map_fill_ratio > 0:
        map_deferred = (
            f"Surface grid fill {map_fill_ratio:.0%} below {_MIN_MAP_FILL:.0%} "
            "— map not published (sparse coupe; check source vs cut Z)."
        )
    elif attempt.ok and decode_ok and punctual:
        map_deferred = (
            "Punctual .recp decoded (energy p^2-homogeneous). "
            "Surface .csbin missing or empty — map not published from punctual."
        )
    elif attempt.ok:
        map_deferred = (
            "SPPS outputs present but punctual decode incomplete; "
            "map not published."
        )
    else:
        map_deferred = "Map deferred: no valid SPPS run (no invented dB)."

    quantity = "energy_p2_homogeneous" if punctual else None
    unit = "Pa2_homogeneous" if punctual else None
    display_quantity = "Lp_dB" if any_lp or map_available else None
    display_unit = "dB" if any_lp or map_available else None

    notes = [
        "Base SPPS does not claim diffraction/interference/modal physics as computed.",
        "Lw != Lp; .recp stores p^2-homogeneous energy; "
        "Lp = 10*log10(E*(1/(20e-6 Pa)^2)) after energy sum.",
        "Zero receiver energy != 0 dB / silence (lpDbGlobal=null).",
    ]
    if map_available:
        notes.append(
            "Surface map from RSBIN .csbin (coupe/face centroids → grid); "
            "not interpolating punctual points."
        )

    return {
        "schemaVersion": "1.0",
        "jobId": job_id,
        "revisionId": revision_id,
        "snapshotHash": snapshot_hash,
        "quantity": quantity,
        "unit": unit,
        "displayQuantity": display_quantity,
        "displayUnit": display_unit,
        "grid": grid,
        "masks": None,
        "artifactPaths": list(attempt.artifact_paths),
        "mapAvailable": map_available,
        "mapDeferredReason": map_deferred,
        "punctualReceivers": punctual,
        "surface": surface,
        "decode": decoded,
        "sci003Golden": {
            "status": "decoder_ok_golden_pending",
            "toleranceDb": 0.1,
            "note": (
                "SCI-003: numerical golden vs I-Simpa GUI on identical inputs "
                "not yet recorded; do not invent reference Lp."
            ),
        },
        "notes": notes,
        "attempt": attempt.to_dict(),
    }


def write_result_manifest(path: Path, manifest: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def write_attempt_report(path: Path, attempt: CalculationAttempt) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(attempt.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
