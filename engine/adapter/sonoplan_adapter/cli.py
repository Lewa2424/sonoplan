"""Minimal CLI for STG-01/04 validation and calculation attempts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .contracts import DEFAULT_OUTPUT_SPECS, OutputFileSpec
from .env import check_spps_environment
from .job_run import (
    attempt_spps_calculation,
    build_result_manifest,
    write_attempt_report,
    write_result_manifest,
)
from .results import RecpDecodeError, decode_spps_workdir, read_punctual_sound_level
from .validate_outputs import evaluate_run


def _load_specs_from_manifest(manifest_path: Path | None) -> tuple[OutputFileSpec, ...]:
    if manifest_path is None:
        return DEFAULT_OUTPUT_SPECS
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    outs = data.get("expected_outputs") or []
    if not outs:
        return DEFAULT_OUTPUT_SPECS
    return tuple(
        OutputFileSpec(
            relative_path=item["path"],
            required=bool(item.get("required", True)),
            min_bytes=int(item.get("min_bytes", 1)),
            description=str(item.get("description", "")),
        )
        for item in outs
    )


def cmd_validate_outputs(args: argparse.Namespace) -> int:
    work = Path(args.work_dir)
    specs = _load_specs_from_manifest(Path(args.manifest) if args.manifest else None)
    # Simulate / inspect a completed run directory. Exit code may be injected
    # for the broken_exit0 fixture (ENG-009 regression).
    result = evaluate_run(
        exit_code=int(args.exit_code),
        work_dir=work,
        specs=specs,
    )
    payload = {
        "ok": result.ok,
        "exit_code": result.exit_code,
        "failure_reasons": result.failure_reasons,
        "output_checks": result.output_checks,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if result.ok else 1


def cmd_check_env(args: argparse.Namespace) -> int:
    status = check_spps_environment(spps_bin=args.spps_bin)
    print(
        json.dumps(
            {
                "ok": status.ok,
                "code": status.code,
                "message": status.message,
                "spps_bin": status.spps_bin,
                "platform": status.platform,
                "is_linux": status.is_linux,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if status.ok else 1


def cmd_attempt_run(args: argparse.Namespace) -> int:
    work = Path(args.work_dir)
    required = tuple(args.required_input) if args.required_input else ("config.xml",)
    attempt = attempt_spps_calculation(
        work_dir=work,
        config_xml_name=args.config,
        spps_bin=args.spps_bin,
        required_inputs=required,
    )
    print(json.dumps(attempt.to_dict(), ensure_ascii=False, indent=2))
    if args.report:
        write_attempt_report(Path(args.report), attempt)
    if args.result_manifest:
        manifest = build_result_manifest(
            job_id=args.job_id or "local-attempt",
            revision_id=args.revision_id or "local-revision",
            snapshot_hash=args.snapshot_hash
            or ("0" * 64),
            attempt=attempt,
        )
        write_result_manifest(Path(args.result_manifest), manifest)
    # Exit 0 only on successful SPPS+outputs. Fixture/env failures use exit 2
    # so CI can distinguish "blocker documented" from crash.
    if attempt.ok:
        return 0
    if attempt.error_code == "FIXTURE_INPUTS_MISSING":
        return 2
    return 1


def cmd_decode_outputs(args: argparse.Namespace) -> int:
    """Decode .recp GABE after SPPS; write ResultManifest JSON (no invented heatmap)."""
    work = Path(args.work_dir)
    if args.recp:
        try:
            decoded = read_punctual_sound_level(Path(args.recp))
        except (RecpDecodeError, OSError) as exc:
            print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
            return 1
        payload = {"ok": True, "punctual": [decoded.summary_dict()]}
        if args.manifest_out:
            from .job_run import CalculationAttempt

            attempt = CalculationAttempt(
                ok=True,
                work_dir=str(work if work.is_dir() else Path(args.recp).parent),
                artifact_paths=[str(Path(args.recp))],
            )
            manifest = build_result_manifest(
                job_id=args.job_id or "decode-only",
                revision_id=args.revision_id or "decode-only",
                snapshot_hash=args.snapshot_hash or ("0" * 64),
                attempt=attempt,
                decoded={
                    "ok": True,
                    "punctual": [decoded.summary_dict()],
                    "errors": [],
                    "statsProbe": None,
                },
            )
            write_result_manifest(Path(args.manifest_out), manifest)
        print(json.dumps(payload, ensure_ascii=True, indent=2))
        return 0

    decoded = decode_spps_workdir(work)
    if args.manifest_out:
        from .job_run import CalculationAttempt

        attempt = CalculationAttempt(
            ok=decoded.ok,
            work_dir=str(work),
            artifact_paths=[
                p.get("relativePath")
                for p in decoded.punctual
                if p.get("relativePath")
            ],
            error_code=None if decoded.ok else "RECP_DECODE_FAILED",
            error_message="; ".join(decoded.errors) or None,
        )
        manifest = build_result_manifest(
            job_id=args.job_id or "decode-workdir",
            revision_id=args.revision_id or "decode-workdir",
            snapshot_hash=args.snapshot_hash or ("0" * 64),
            attempt=attempt,
            decoded=decoded.to_dict(),
        )
        write_result_manifest(Path(args.manifest_out), manifest)
    print(json.dumps(decoded.to_dict(), ensure_ascii=True, indent=2))
    return 0 if decoded.ok else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sonoplan_adapter")
    sub = parser.add_subparsers(dest="command", required=True)

    p_val = sub.add_parser(
        "validate-outputs",
        help="Validate SPPS workdir outputs (exit 0 ≠ success)",
    )
    p_val.add_argument("work_dir")
    p_val.add_argument("--manifest", default=None)
    p_val.add_argument(
        "--exit-code",
        type=int,
        default=0,
        help="Process exit code to evaluate (default 0 — the dangerous case)",
    )
    p_val.set_defaults(func=cmd_validate_outputs)

    p_env = sub.add_parser("check-env", help="Check SPPS_BIN / Linux host gates")
    p_env.add_argument("--spps-bin", default=None)
    p_env.set_defaults(func=cmd_check_env)

    p_run = sub.add_parser(
        "attempt-run",
        help="Attempt SPPS on a workdir (fails clearly if inputs/env missing)",
    )
    p_run.add_argument("work_dir")
    p_run.add_argument("--config", default="config.xml")
    p_run.add_argument("--spps-bin", default=None)
    p_run.add_argument(
        "--required-input",
        action="append",
        default=None,
        help="Required input filename (repeatable; default config.xml)",
    )
    p_run.add_argument("--report", default=None, help="Write JSON attempt report path")
    p_run.add_argument(
        "--result-manifest",
        default=None,
        help="Write ResultManifest JSON after attempt (decode .recp when present)",
    )
    p_run.add_argument("--job-id", default=None)
    p_run.add_argument("--revision-id", default=None)
    p_run.add_argument("--snapshot-hash", default=None)
    p_run.set_defaults(func=cmd_attempt_run)

    p_dec = sub.add_parser(
        "decode-outputs",
        help="Decode punctual Sound level.recp (GABE) → energy/Lp + ResultManifest",
    )
    p_dec.add_argument(
        "work_dir",
        nargs="?",
        default=".",
        help="SPPS work directory containing Punctual receivers/",
    )
    p_dec.add_argument(
        "--recp",
        default=None,
        help="Decode a single .recp path instead of scanning work_dir",
    )
    p_dec.add_argument(
        "--manifest-out",
        default=None,
        help="Write ResultManifest JSON path",
    )
    p_dec.add_argument("--job-id", default=None)
    p_dec.add_argument("--revision-id", default=None)
    p_dec.add_argument("--snapshot-hash", default=None)
    p_dec.set_defaults(func=cmd_decode_outputs)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
