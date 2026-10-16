"""Decode real CI .recp / GABE fixtures — no invented dB values."""

from __future__ import annotations

import json
import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sonoplan_adapter.gabe import GabeObjectType, load_gabe
from sonoplan_adapter.results import (
    P0_INV_PREF2,
    RecpDecodeError,
    energy_to_lp_db,
    read_punctual_sound_level,
)

FIXTURE_EXPECTED = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "minimal_room"
    / "expected"
)
RECP = FIXTURE_EXPECTED / "Punctual receivers" / "r_front" / "Sound level.recp"
STATS = FIXTURE_EXPECTED / "statsSPPS.gabe"


class EnergyToLpTest(unittest.TestCase):
    def test_zero_energy_is_null_not_zero_db(self) -> None:
        lp, reason = energy_to_lp_db(0.0)
        self.assertIsNone(lp)
        self.assertEqual(reason, "zero_energy_not_silence")

    def test_matches_isimpa_formula(self) -> None:
        # Lp = 10*log10(E * 1/(20e-6)^2)  — e_report_gabe_recp.cpp
        energy = 4.0e-10  # == pref² → 0 dB
        lp, reason = energy_to_lp_db(energy)
        self.assertIsNone(reason)
        assert lp is not None
        self.assertAlmostEqual(lp, 0.0, places=6)
        self.assertAlmostEqual(10.0 * math.log10(energy * P0_INV_PREF2), lp)


@unittest.skipUnless(RECP.is_file(), "expected Sound level.recp fixture missing")
class RealRecpFixtureTest(unittest.TestCase):
    def test_gabe_structure_matches_upstream_layout(self) -> None:
        table = load_gabe(RECP)
        self.assertEqual(table.format_version, 2)
        self.assertGreaterEqual(table.ncols, 2)
        self.assertEqual(table.columns[0].col_type, GabeObjectType.SHORTSTRING)
        self.assertTrue(table.columns[0].strings)
        self.assertTrue(table.columns[0].strings[0].endswith("ms"))
        float_cols = [c for c in table.columns if c.col_type is GabeObjectType.FLOAT]
        self.assertGreaterEqual(len(float_cols), 1)
        self.assertTrue(any("Hz" in c.label for c in float_cols))

    def test_punctual_decode_documents_energy_not_invented_db(self) -> None:
        decoded = read_punctual_sound_level(RECP)
        self.assertEqual(decoded.quantity_in_file, "energy_p2_homogeneous")
        self.assertEqual(decoded.band_labels, ("100 Hz", "1000 Hz"))
        self.assertGreaterEqual(len(decoded.time_labels), 1)
        # Honesty: zero energy → lp null (not 0 dB). Nonzero → finite lpDb.
        if decoded.energy_sum_global == 0.0:
            self.assertIsNone(decoded.lp_db_global)
            self.assertEqual(decoded.lp_db_global_reason, "zero_energy_not_silence")
            for band in decoded.bands:
                self.assertEqual(band.energy_sum, 0.0)
                self.assertIsNone(band.lp_db)
        else:
            self.assertIsNotNone(decoded.lp_db_global)
            assert decoded.lp_db_global is not None
            self.assertEqual(decoded.lp_db_global, decoded.lp_db_global)  # not NaN
            self.assertGreater(decoded.energy_sum_global, 0.0)
            self.assertTrue(any(b.nonzero_timesteps > 0 for b in decoded.bands))

    def test_corrupt_file_raises(self) -> None:
        with self.assertRaises(RecpDecodeError):
            read_punctual_sound_level(FIXTURE_EXPECTED / "does-not-exist.recp")


@unittest.skipUnless(STATS.is_file(), "expected statsSPPS.gabe fixture missing")
class StatsGabeFixtureTest(unittest.TestCase):
    def test_stats_particles_remaining(self) -> None:
        table = load_gabe(STATS)
        labels = table.columns[0].strings
        assert labels is not None
        self.assertIn("Total", labels[-1])
        for col in table.columns[1:]:
            self.assertEqual(col.col_type, GabeObjectType.INT)
            assert col.ints is not None
            # Total row == launched particles for that band (fixture nbparticules).
            total_idx = list(labels).index("Total")
            self.assertGreater(col.ints[total_idx], 0)


class GoldenPendingHonestyTest(unittest.TestCase):
    def test_manifest_declares_golden_pending(self) -> None:
        manifest_path = (
            Path(__file__).resolve().parents[2]
            / "fixtures"
            / "minimal_room"
            / "manifest.json"
        )
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertIsNone(data.get("golden_values"))
        self.assertIn("decoder_ok_golden_pending", data.get("golden_status", ""))


if __name__ == "__main__":
    unittest.main()
