"""A-weighting (IEC 61672-1) applied once to unweighted band levels.

Same values as packages/domain/src/aWeighting.ts (31.5 Hz omitted: SPPS band
labels are integers). Bands combine by energy
(10^(L/10)), never by adding dB.
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence

A_WEIGHTING_DB: dict[int, float] = {
    20: -50.5,
    25: -44.7,
    40: -34.6,
    50: -30.2,
    63: -26.2,
    80: -22.5,
    100: -19.1,
    125: -16.1,
    160: -13.4,
    200: -10.9,
    250: -8.6,
    315: -6.6,
    400: -4.8,
    500: -3.2,
    630: -1.9,
    800: -0.8,
    1000: 0.0,
    1250: 0.6,
    1600: 1.0,
    2000: 1.2,
    2500: 1.3,
    3150: 1.2,
    4000: 1.0,
    5000: 0.5,
    6300: -0.1,
    8000: -1.1,
    10000: -2.5,
    12500: -4.3,
    16000: -6.6,
    20000: -9.3,
}

_BAND_LABEL = re.compile(r"^\s*(\d+)\s*Hz\s*$")


class UnknownBandError(ValueError):
    """Band has no tabulated A-weighting (not a nominal octave / third-octave)."""


def band_hz_from_label(label: str) -> int:
    """SPPS GABE column label ``"1000 Hz"`` → 1000."""
    m = _BAND_LABEL.match(label)
    if not m:
        raise UnknownBandError(f"not a band label: {label!r}")
    return int(m.group(1))


def a_weighting_db(band_hz: int) -> float:
    try:
        return A_WEIGHTING_DB[band_hz]
    except KeyError as exc:
        raise UnknownBandError(f"A-weighting unknown for {band_hz} Hz") from exc


def a_weighted_energy(energy_by_band_hz: Mapping[int, float]) -> float:
    """Σ E_band · 10^(A_band/10) — p²-homogeneous A-weighted energy."""
    return float(
        sum(e * 10.0 ** (a_weighting_db(hz) / 10.0) for hz, e in energy_by_band_hz.items())
    )


def a_weighted_level_grid(
    lp_by_band_hz: Mapping[int, Sequence[float | None]],
) -> list[float | None]:
    """Cell-wise LA from per-band Lp grids of identical layout.

    A cell with no energy in any band stays ``None`` (not 0 dB).
    """
    if not lp_by_band_hz:
        raise ValueError("no band grids")
    sizes = {len(g) for g in lp_by_band_hz.values()}
    if len(sizes) != 1:
        raise ValueError(f"band grids differ in size: {sorted(sizes)}")
    n = sizes.pop()
    weights = {hz: 10.0 ** (a_weighting_db(hz) / 10.0) for hz in lp_by_band_hz}
    out: list[float | None] = []
    for k in range(n):
        total = 0.0
        for hz, grid in lp_by_band_hz.items():
            lp = grid[k]
            if lp is not None:
                total += weights[hz] * 10.0 ** (lp / 10.0)
        out.append(10.0 * math.log10(total) if total > 0 else None)
    return out
