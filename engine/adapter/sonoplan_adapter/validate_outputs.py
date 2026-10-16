"""Validate SPPS outputs. Exit code 0 is necessary but never sufficient (ENG-009)."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from .contracts import DEFAULT_OUTPUT_SPECS, OutputFileSpec, SppsRunResult


class OutputValidationError(Exception):
    """Raised when outputs are missing, empty, or structurally invalid."""


def check_output_files(
    work_dir: Path,
    specs: Iterable[OutputFileSpec] = DEFAULT_OUTPUT_SPECS,
) -> list[dict]:
    """Return per-file check records. Does not decode binary payloads yet."""
    records: list[dict] = []
    for spec in specs:
        path = work_dir / spec.relative_path
        exists = path.is_file()
        size = path.stat().st_size if exists else 0
        ok = exists and size >= spec.min_bytes
        records.append(
            {
                "path": spec.relative_path,
                "required": spec.required,
                "exists": exists,
                "size_bytes": size,
                "min_bytes": spec.min_bytes,
                "ok": ok if spec.required else (ok or not exists),
                "description": spec.description,
            }
        )
    return records


def evaluate_run(
    *,
    exit_code: int,
    work_dir: Path,
    stdout: str = "",
    stderr: str = "",
    duration_s: float = 0.0,
    specs: Iterable[OutputFileSpec] = DEFAULT_OUTPUT_SPECS,
) -> SppsRunResult:
    """Decide success from exit code AND output integrity.

    Documented upstream issue (ENG-009 / TZ S05): main() often returns 0 even
    when MainProcess fails. Missing/empty required outputs => failed.
    """
    reasons: list[str] = []
    checks = check_output_files(work_dir, specs)

    # Non-zero exit is always a failure signal when present.
    if exit_code != 0:
        reasons.append(f"spps_exit_code={exit_code}")

    for rec in checks:
        if rec["required"] and not rec["ok"]:
            if not rec["exists"]:
                reasons.append(f"missing_required_output:{rec['path']}")
            else:
                reasons.append(
                    f"empty_or_too_small_output:{rec['path']} size={rec['size_bytes']}"
                )

    # Critical: exit 0 with no valid outputs must fail (do not publish a map).
    if exit_code == 0 and any(
        r["required"] and not r["ok"] for r in checks
    ):
        if "exit_0_without_valid_outputs" not in "".join(reasons):
            reasons.append("exit_0_without_valid_outputs")

    return SppsRunResult(
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
        duration_s=duration_s,
        work_dir=str(work_dir),
        output_checks=checks,
        ok=len(reasons) == 0,
        failure_reasons=reasons,
    )


def assert_run_ok(result: SppsRunResult) -> None:
    if not result.ok:
        raise OutputValidationError(
            "; ".join(result.failure_reasons) or "spps_run_failed"
        )
