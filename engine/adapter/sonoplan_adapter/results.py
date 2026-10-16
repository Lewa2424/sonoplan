"""Binary result readers for SPPS outputs.

ENG-006: decode only with a tested procedure against real files.
`.recp` is GABE (libsimpa), not CSV — see Docs/file_recp.rst + gabe.cpp Load().

File contents (upstream Docs/file_recp.rst @ I-Simpa):
  temporal evolution by frequency band of a quantity homogeneous to
  instantaneous squared sound pressure (p²). Display as SPL is a GUI
  post-process, not what SPPS stores on disk.

I-Simpa GUI conversion (e_report_gabe_recp.cpp::GetArrayData):
  p_0 = 1 / (20e-6)²
  Lp_dB = 10 * log10(w * p_0)   after summing energy (never sum dB)
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .gabe import GabeFormatError, GabeObjectType, load_gabe

# I-Simpa: const float p_0 = 1/pow((float)(20*pow(10.f,(int)-6)),(int)2);
PREF_PA = 20e-6
P0_INV_PREF2 = 1.0 / (PREF_PA * PREF_PA)

QUANTITY_IN_FILE = "energy_p2_homogeneous"
UNIT_IN_FILE = "Pa2_homogeneous"
QUANTITY_DISPLAY = "Lp_dB"
UNIT_DISPLAY = "dB"
SOURCE_DOC = (
    "I-Simpa Docs/file_recp.rst + e_report_gabe_recp.cpp GetArrayData @ "
    "929a5c8e5f590b189f29155faeff8670f3699479"
)
# ASCII-only strings for Windows cp1251 consoles / JSON logs.
CONVERSION_NOTE = "Lp_dB = 10*log10(energy_sum * (1/(20e-6 Pa)^2)) after energy sum"
FILE_CONTENT_NOTES = (
    "Disk values are p^2-homogeneous energy, not SPL.",
    "Zero energy sum -> lp_db is null (not 0 dB / silence).",
    "A-weighting is not applied here; apply once to unweighted bands only.",
)


@dataclass(frozen=True)
class BinaryProbe:
    path: str
    size_bytes: int
    magic_hex: str
    note: str


class BinaryDecodeNotReady(NotImplementedError):
    """Decoder awaits real binary samples under engine/fixtures/*/expected/."""


class RecpDecodeError(ValueError):
    """`.recp` present but not a valid punctual sound-level GABE table."""


@dataclass(frozen=True)
class BandEnergy:
    band_label: str
    energy_sum: float
    lp_db: float | None
    lp_db_reason: str | None
    nonzero_timesteps: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PunctualSoundLevel:
    """Decoded punctual receiver Sound level.recp (energy grid + optional Lp)."""

    path: str
    format_version: int
    time_labels: tuple[str, ...]
    band_labels: tuple[str, ...]
    # shape: band index → tuple of energy per time step (same length as time_labels)
    energy_by_band: tuple[tuple[float, ...], ...]
    bands: tuple[BandEnergy, ...]
    energy_sum_global: float
    lp_db_global: float | None
    lp_db_global_reason: str | None
    quantity_in_file: str = QUANTITY_IN_FILE
    unit_in_file: str = UNIT_IN_FILE
    display_quantity: str = QUANTITY_DISPLAY
    display_unit: str = UNIT_DISPLAY
    conversion: str = CONVERSION_NOTE
    source_doc: str = SOURCE_DOC
    notes: tuple[str, ...] = FILE_CONTENT_NOTES

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "formatVersion": self.format_version,
            "quantityInFile": self.quantity_in_file,
            "unitInFile": self.unit_in_file,
            "displayQuantity": self.display_quantity,
            "displayUnit": self.display_unit,
            "conversion": self.conversion,
            "sourceDoc": self.source_doc,
            "timeLabels": list(self.time_labels),
            "bandLabels": list(self.band_labels),
            "timestepCount": len(self.time_labels),
            "bandCount": len(self.band_labels),
            "bands": [b.to_dict() for b in self.bands],
            "energySumGlobal": self.energy_sum_global,
            "lpDbGlobal": self.lp_db_global,
            "lpDbGlobalReason": self.lp_db_global_reason,
            "notes": list(self.notes),
            # Full energy grid kept for golden/debug; omit from default manifest if huge.
            "energyByBand": [list(row) for row in self.energy_by_band],
        }

    def summary_dict(self) -> dict[str, Any]:
        """Manifest-sized summary without full echogram grid."""
        full = self.to_dict()
        full.pop("energyByBand", None)
        full.pop("timeLabels", None)
        return full


def probe_binary(path: Path, max_magic_bytes: int = 16) -> BinaryProbe:
    data = path.read_bytes()[:max_magic_bytes]
    return BinaryProbe(
        path=str(path),
        size_bytes=path.stat().st_size,
        magic_hex=data.hex(),
        note="probe only — no acoustic decoding",
    )


def energy_to_lp_db(energy: float) -> tuple[float | None, str | None]:
    """I-Simpa GetArrayData conversion. Zero energy → null (not 0 dB)."""
    if energy < 0:
        return None, "negative_energy"
    if energy == 0.0:
        return None, "zero_energy_not_silence"
    product = energy * P0_INV_PREF2
    if product <= 0.0:
        return None, "non_positive_after_scale"
    return 10.0 * math.log10(product), None


def read_punctual_sound_level(path: Path | str) -> PunctualSoundLevel:
    """Decode punctual receiver Sound level.recp (GABE) to documented quantities."""
    p = Path(path)
    try:
        table = load_gabe(p)
    except (GabeFormatError, OSError) as exc:
        raise RecpDecodeError(str(exc)) from exc

    if not table.columns:
        raise RecpDecodeError("empty GABE table")

    time_col = table.columns[0]
    if time_col.col_type is not GabeObjectType.SHORTSTRING or time_col.strings is None:
        raise RecpDecodeError(
            "expected first column SHORTSTRING time labels "
            f"(got {time_col.col_type.name})"
        )

    band_cols = []
    for col in table.columns[1:]:
        if col.col_type is GabeObjectType.FLOAT and col.floats is not None:
            if len(col.floats) != len(time_col.strings):
                raise RecpDecodeError(
                    f"band {col.label!r} rows={len(col.floats)} "
                    f"!= time rows={len(time_col.strings)}"
                )
            band_cols.append(col)
        # Ignore unexpected trailing columns rather than inventing values.

    if not band_cols:
        raise RecpDecodeError("no FLOAT frequency-band columns after time labels")

    energy_by_band: list[tuple[float, ...]] = []
    bands: list[BandEnergy] = []
    for col in band_cols:
        assert col.floats is not None
        energy_sum = float(sum(col.floats))
        lp, reason = energy_to_lp_db(energy_sum)
        energy_by_band.append(col.floats)
        bands.append(
            BandEnergy(
                band_label=col.label,
                energy_sum=energy_sum,
                lp_db=lp,
                lp_db_reason=reason,
                nonzero_timesteps=sum(1 for v in col.floats if v != 0.0),
            )
        )

    energy_global = float(sum(b.energy_sum for b in bands))
    lp_global, lp_global_reason = energy_to_lp_db(energy_global)

    return PunctualSoundLevel(
        path=str(p),
        format_version=table.format_version,
        time_labels=time_col.strings,
        band_labels=tuple(c.label for c in band_cols),
        energy_by_band=tuple(energy_by_band),
        bands=tuple(bands),
        energy_sum_global=energy_global,
        lp_db_global=lp_global,
        lp_db_global_reason=lp_global_reason,
    )


def read_surface_csbin(path: Path | str):
    """Decode surface / coupe .csbin (RSBIN). See ``rsbin_io``."""
    from .rsbin_io import CsbinDecodeError, read_surface_csbin as _read

    try:
        return _read(path)
    except CsbinDecodeError as exc:
        raise RecpDecodeError(str(exc)) from exc


@dataclass
class DecodedWorkdir:
    """Post-SPPS decode of known punctual outputs in a work directory."""

    ok: bool
    punctual: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    stats_probe: dict[str, Any] | None = None
    surface: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "punctual": list(self.punctual),
            "errors": list(self.errors),
            "statsProbe": self.stats_probe,
            "surface": self.surface,
        }


def decode_spps_workdir(work_dir: Path) -> DecodedWorkdir:
    """Find and decode Sound level.recp + optional surface .csbin; probe stats."""
    work = work_dir.resolve()
    errors: list[str] = []
    punctual: list[dict[str, Any]] = []

    receivers_root = work / "Punctual receivers"
    if receivers_root.is_dir():
        for recp in sorted(receivers_root.glob("*/Sound level.recp")):
            receiver_id = recp.parent.name
            try:
                decoded = read_punctual_sound_level(recp)
                summary = decoded.summary_dict()
                summary["receiverId"] = receiver_id
                relative = str(recp.relative_to(work)).replace("\\", "/")
                summary["relativePath"] = relative
                punctual.append(summary)
            except (RecpDecodeError, OSError) as exc:
                errors.append(f"{recp}: {exc}")
    else:
        errors.append("Punctual receivers/ directory missing")

    stats_probe: dict[str, Any] | None = None
    stats_path = work / "statsSPPS.gabe"
    if stats_path.is_file():
        try:
            table = load_gabe(stats_path)
            stats_probe = {
                "path": str(stats_path.relative_to(work)).replace("\\", "/"),
                "formatVersion": table.format_version,
                "columns": [
                    {
                        "label": c.label,
                        "colType": c.col_type.name,
                        "rows": c.rows,
                        "ints": list(c.ints) if c.ints is not None else None,
                        "strings": list(c.strings) if c.strings is not None else None,
                    }
                    for c in table.columns
                ],
                "note": (
                    "Particle statistics GABE; not Lp. "
                    "Zero receiver energy may coexist with remaining particles."
                ),
            }
        except GabeFormatError as exc:
            errors.append(f"statsSPPS.gabe: {exc}")

    surface: dict[str, Any] | None = None
    csbin_candidates = [
        work / "recepteurss" / "Global" / "rs_cut.csbin",
        work / "recepteurss" / "rs_cut.csbin",
        work / "rs_cut.csbin",
        work / "recepteurss" / "Global" / "Sound_level.csbin",
        work / "recepteurss" / "Sound_level.csbin",
        work / "Sound_level.csbin",
        # Legacy bug: folder without trailing slash → recepteurssGlobal/
        work / "recepteurssGlobal" / "rs_cut.csbin",
        work / "recepteurssGlobal" / "Sound_level.csbin",
    ]
    for extra_dir in (
        work / "recepteurss" / "Global",
        work / "recepteurssGlobal",
        work / "recepteurss",
    ):
        if extra_dir.is_dir():
            for found in sorted(extra_dir.glob("*.csbin")):
                if found not in csbin_candidates:
                    csbin_candidates.append(found)
    for csbin in csbin_candidates:
        if not csbin.is_file():
            continue
        try:
            decoded_s = read_surface_csbin(csbin)
            surface = decoded_s.to_dict()
            surface["relativePath"] = str(csbin.relative_to(work)).replace(
                "\\", "/"
            )
            break
        except (RecpDecodeError, OSError, BinaryDecodeNotReady) as exc:
            errors.append(f"{csbin}: {exc}")

    punctual_errors = [e for e in errors if "Sound level.recp" in e]
    ok = bool(punctual) and not punctual_errors
    return DecodedWorkdir(
        ok=ok,
        punctual=punctual,
        errors=errors,
        stats_probe=stats_probe,
        surface=surface,
    )
