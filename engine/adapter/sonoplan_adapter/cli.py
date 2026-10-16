"""Minimal CLI for STG-01/04 validation and calculation attempts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .contracts import DEFAULT_OUTPUT_SPECS, OutputFileSpec
from .env import check_spps_environment
from .job_run import attempt_spps_calculation, write_attempt_report
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
    # Exit 0 only on successful SPPS+outputs. Fixture/env failures use exit 2
    # so CI can distinguish "blocker documented" from crash.
    if attempt.ok:
        return 0
    if attempt.error_code == "FIXTURE_INPUTS_MISSING":
        return 2
    return 1


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
    p_run.set_defaults(func=cmd_attempt_run)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
