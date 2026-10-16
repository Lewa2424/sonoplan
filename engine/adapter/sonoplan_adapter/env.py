"""SPPS binary environment checks for worker / CI (no fake acoustic results)."""

from __future__ import annotations

import os
import platform
import sys
from dataclasses import dataclass
from pathlib import Path


# Stable error codes for job.failed (API / worker / CI).
CODE_SPPS_BIN_MISSING = "SPPS_BIN_MISSING"
CODE_SPPS_NOT_LINUX = "SPPS_NOT_LINUX"
CODE_SPPS_EXECUTABLE_NOT_FOUND = "SPPS_EXECUTABLE_NOT_FOUND"
CODE_SPPS_NOT_ELF = "SPPS_NOT_ELF"
CODE_FIXTURE_INPUTS_MISSING = "FIXTURE_INPUTS_MISSING"
CODE_SPPS_RUN_FAILED = "SPPS_RUN_FAILED"


@dataclass(frozen=True)
class SppsEnvStatus:
    ok: bool
    code: str | None
    message: str
    spps_bin: str | None
    platform: str
    is_linux: bool


def is_linux_host() -> bool:
    return sys.platform.startswith("linux")


def resolve_spps_bin(explicit: str | None = None) -> str | None:
    if explicit:
        return explicit
    env = os.environ.get("SPPS_BIN", "").strip()
    return env or None


def probe_elf_magic(path: Path) -> bool:
    """True if file starts with ELF magic (Linux binary)."""
    try:
        with path.open("rb") as fh:
            return fh.read(4) == b"\x7fELF"
    except OSError:
        return False


def check_spps_environment(*, spps_bin: str | None = None) -> SppsEnvStatus:
    """Gate before launching SPPS. Never invents acoustic outputs."""
    host = platform.system()
    linux = is_linux_host()
    resolved = resolve_spps_bin(spps_bin)

    if not linux:
        return SppsEnvStatus(
            ok=False,
            code=CODE_SPPS_NOT_LINUX,
            message=(
                f"SPPS Linux binary cannot run on this host ({host}). "
                "Use a Linux worker / GitHub Actions; do not execute the CI ELF on Windows."
            ),
            spps_bin=resolved,
            platform=host,
            is_linux=False,
        )

    if not resolved:
        return SppsEnvStatus(
            ok=False,
            code=CODE_SPPS_BIN_MISSING,
            message="SPPS_BIN is not set. Point it at the Linux spps binary from the CI artifact.",
            spps_bin=None,
            platform=host,
            is_linux=True,
        )

    path = Path(resolved)
    if not path.is_file():
        return SppsEnvStatus(
            ok=False,
            code=CODE_SPPS_EXECUTABLE_NOT_FOUND,
            message=f"SPPS_BIN path does not exist or is not a file: {resolved}",
            spps_bin=resolved,
            platform=host,
            is_linux=True,
        )

    if not probe_elf_magic(path):
        return SppsEnvStatus(
            ok=False,
            code=CODE_SPPS_NOT_ELF,
            message=f"SPPS_BIN is not an ELF binary: {resolved}",
            spps_bin=resolved,
            platform=host,
            is_linux=True,
        )

    return SppsEnvStatus(
        ok=True,
        code=None,
        message="SPPS environment OK",
        spps_bin=str(path.resolve()),
        platform=host,
        is_linux=True,
    )


def fixture_inputs_ready(work_dir: Path, required: tuple[str, ...] = ("config.xml",)) -> bool:
    return all((work_dir / name).is_file() for name in required)
