"""Launch SPPS as a subprocess (ENG-004). No shell string concatenation."""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

from .contracts import SppsRunRequest, SppsRunResult
from .validate_outputs import evaluate_run


def run_spps(request: SppsRunRequest) -> SppsRunResult:
    work = Path(request.work_dir).resolve()
    if not work.is_dir():
        return SppsRunResult(
            exit_code=-1,
            stdout="",
            stderr=f"work_dir_missing:{work}",
            duration_s=0.0,
            work_dir=str(work),
            ok=False,
            failure_reasons=[f"work_dir_missing:{work}"],
        )

    config = work / request.config_xml_name
    if not config.is_file():
        return SppsRunResult(
            exit_code=-1,
            stdout="",
            stderr=f"config_missing:{config}",
            duration_s=0.0,
            work_dir=str(work),
            ok=False,
            failure_reasons=[f"config_missing:{config.name}"],
        )

    env = os.environ.copy()
    env.update(request.env)
    # Fixed locale for numeric consistency (ENG-007).
    env.setdefault("LC_ALL", "C")
    env.setdefault("LANG", "C")

    argv = request.argv()
    # Replace executable name with absolute path if provided as path.
    exe = request.spps_executable
    cmd = [exe, *argv[1:]]

    t0 = time.perf_counter()
    try:
        completed = subprocess.run(
            cmd,
            cwd=str(work),
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            shell=False,
            check=False,
        )
    except FileNotFoundError as exc:
        return SppsRunResult(
            exit_code=-1,
            stdout="",
            stderr=str(exc),
            duration_s=time.perf_counter() - t0,
            work_dir=str(work),
            ok=False,
            failure_reasons=[f"spps_executable_not_found:{exe}"],
        )

    return evaluate_run(
        exit_code=completed.returncode,
        work_dir=work,
        stdout=completed.stdout or "",
        stderr=completed.stderr or "",
        duration_s=time.perf_counter() - t0,
    )
