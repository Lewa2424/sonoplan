"""Input/output contracts for the SPPS adapter boundary.

These schemas are stubbed for STG-01. Full OpenAPI lives in packages/contracts
once the parallel scaffold lands; keep this module free of network/DB imports.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class QuantityKind(str, Enum):
    """Acoustic quantity kinds — Lw and Lp must never be confused."""

    SOUND_POWER_LEVEL_LW = "Lw_dB"
    SOUND_PRESSURE_LEVEL_LP = "Lp_dB"
    ENERGY_DENSITY = "energy_Pa2"  # placeholder until CAL-009 procedure is confirmed
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class SppsRunRequest:
    """Parameters to launch the SPPS process (ENG-004).

    argv is a list — never shell-joined. Config path is the primary argument.
    """

    work_dir: str
    config_xml_name: str = "config.xml"
    spps_executable: str = "spps"
    verbose: bool = False
    env: dict[str, str] = field(default_factory=dict)

    def argv(self) -> list[str]:
        args = [self.spps_executable]
        if self.verbose:
            # Upstream supports a verbose flag in inspected builds; exact flag
            # must be confirmed against pinned commit before production use.
            args.append("-v")
        args.append(self.config_xml_name)
        return args


@dataclass
class OutputFileSpec:
    """Expected artifact after SPPS run."""

    relative_path: str
    required: bool
    min_bytes: int = 1
    description: str = ""


@dataclass
class SppsRunResult:
    """Raw process outcome — not yet a published ResultManifest."""

    exit_code: int
    stdout: str
    stderr: str
    duration_s: float
    work_dir: str
    output_checks: list[dict[str, Any]] = field(default_factory=list)
    ok: bool = False
    failure_reasons: list[str] = field(default_factory=list)


# Default expected outputs for the minimal fixture (per-receiver folder layout
# from I-Simpa BaseReportManager::SauveRecepteursPonctuels). Binary formats TBD decode.
DEFAULT_OUTPUT_SPECS: tuple[OutputFileSpec, ...] = (
    OutputFileSpec(
        relative_path="Punctual receivers/r_front/Sound level.recp",
        required=True,
        min_bytes=1,
        description="Punctual receiver sound level for r_front (binary .recp, not CSV)",
    ),
    OutputFileSpec(
        relative_path="statsSPPS.gabe",
        required=False,
        min_bytes=1,
        description="SPPS statistics (gabe); particle-loss ratio lives here when present",
    ),
)
