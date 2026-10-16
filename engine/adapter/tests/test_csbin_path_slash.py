"""Regression: SPPS joins recepteurss_directory + 'Global' without extra sep."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sonoplan_adapter.export_revision import (  # noqa: E402
    compact_export_payload,
    write_spps_workdir,
)
from sonoplan_adapter.results import decode_spps_workdir  # noqa: E402
from sonoplan_adapter.rsbin_io import write_synthetic_csbin  # noqa: E402


def _snap() -> dict:
    return {
        "schemaVersion": "1.0",
        "rooms": [
            {
                "id": "r1",
                "floorContour": [
                    {"x": 0, "y": 0},
                    {"x": 10, "y": 0},
                    {"x": 10, "y": 8},
                    {"x": 0, "y": 8},
                ],
                "heightM": {"value": 4, "unit": "m"},
                "materialVersionId": "m1",
            }
        ],
        "materials": [
            {
                "id": "m1",
                "catalogKey": "x",
                "name": "x",
                "version": "1",
                "estimated": True,
                "absorptionByBand": [{"bandHz": 1000, "alpha": 0.05}],
            }
        ],
        "sources": [
            {
                "id": "s1",
                "name": "s",
                "position": {"x": 2, "y": 2, "z": 1},
                "powerSpectrumLw": [
                    {"bandHz": 1000, "level": {"value": 90, "unit": "dB"}}
                ],
            }
        ],
        "workplaces": [
            {
                "id": "w1",
                "name": "w",
                "position": {"x": 5, "y": 4, "z": 0},
                "receiverHeightM": {"value": 1.5, "unit": "m"},
            }
        ],
        "solids": [],
    }


class CsbinPathSlashTests(unittest.TestCase):
    def test_export_directory_has_trailing_slash(self) -> None:
        fixture = ROOT.parent / "fixtures" / "minimal_room" / "inputs"
        if not (fixture / "mesh.cbin").is_file():
            self.skipTest("fixture mesh missing")
        payload = compact_export_payload(_snap())
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            write_spps_workdir(
                payload=payload, out_dir=out, fixture_inputs=fixture
            )
            cfg = (out / "config.xml").read_text(encoding="utf-8")
            self.assertIn('recepteurss_directory="recepteurss/"', cfg)

    def test_decode_legacy_recepteurssGlobal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            legacy = work / "recepteurssGlobal"
            legacy.mkdir()
            write_synthetic_csbin(
                legacy / "rs_cut.csbin",
                nodes=[
                    (0.0, 0.0, 1.5),
                    (1.0, 0.0, 1.5),
                    (0.0, 1.0, 1.5),
                    (1.0, 1.0, 1.5),
                ],
                faces=[(0, 1, 2, 1.0), (1, 3, 2, 1.0)],
            )
            decoded = decode_spps_workdir(work)
            self.assertIsNotNone(decoded.surface)
            assert decoded.surface is not None
            self.assertIn("recepteurssGlobal", decoded.surface["relativePath"])


if __name__ == "__main__":
    unittest.main()
