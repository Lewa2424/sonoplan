"""Binary result readers — stubs until real fixtures from a successful SPPS run exist.

ENG-006: do not treat extensions as CSV. Decode only with a tested procedure
against real files from the pinned I-Simpa build.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class BinaryProbe:
    path: str
    size_bytes: int
    magic_hex: str
    note: str


class BinaryDecodeNotReady(NotImplementedError):
    """Decoder awaits real binary samples under engine/fixtures/*/expected/."""


def probe_binary(path: Path, max_magic_bytes: int = 16) -> BinaryProbe:
    data = path.read_bytes()[:max_magic_bytes]
    return BinaryProbe(
        path=str(path),
        size_bytes=path.stat().st_size,
        magic_hex=data.hex(),
        note="probe only — no acoustic decoding",
    )


def read_punctual_sound_level(_path: Path) -> None:
    """Placeholder for .recp / Sound level decode (libsimpa or documented decoder)."""
    raise BinaryDecodeNotReady(
        "Need real SPPS output from pinned build before implementing .recp decode (ENG-006)."
    )


def read_surface_csbin(_path: Path) -> None:
    """Placeholder for surface receiver .csbin decode."""
    raise BinaryDecodeNotReady(
        "Need real SPPS output from pinned build before implementing .csbin decode (ENG-006)."
    )
