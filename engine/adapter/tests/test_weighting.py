"""A-weighting once per band, energy sum (never dB arithmetic)."""

from __future__ import annotations

import math
import unittest

from sonoplan_adapter.weighting import (
    UnknownBandError,
    a_weighted_level_grid,
    band_hz_from_label,
)


class WeightingTests(unittest.TestCase):
    def test_band_label(self) -> None:
        self.assertEqual(band_hz_from_label("1000 Hz"), 1000)
        with self.assertRaises(UnknownBandError):
            band_hz_from_label("Global")

    def test_grid_energy_sum_and_null_cells(self) -> None:
        la = a_weighted_level_grid({1000: [80.0, None, None], 63: [80.0, 90.0, None]})
        assert la[0] is not None and la[1] is not None
        self.assertAlmostEqual(la[0], 10 * math.log10(10**8 + 10 ** (8 - 2.62)), places=9)
        self.assertAlmostEqual(la[1], 90.0 - 26.2, places=9)
        self.assertIsNone(la[2])

    def test_unknown_band_refused(self) -> None:
        with self.assertRaises(UnknownBandError):
            a_weighted_level_grid({1100: [80.0]})

    def test_mismatched_grids_refused(self) -> None:
        with self.assertRaises(ValueError):
            a_weighted_level_grid({1000: [80.0], 500: [80.0, 70.0]})


if __name__ == "__main__":
    unittest.main()
