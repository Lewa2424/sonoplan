"""Minimal CLI for STG-01 validation helpers."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .contracts import DEFAULT_OUTPUT_SPECS, OutputFileSpec
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

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
