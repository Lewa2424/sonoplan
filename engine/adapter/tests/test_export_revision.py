"""Unit tests for Phase 2A revision → box SPPS workdir export."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sonoplan_adapter.cbin_io import read_cbin, scale_cbin_file_inplace
from sonoplan_adapter.export_revision import (
    compact_export_payload,
    write_spps_workdir,
)
from sonoplan_adapter.mbin_io import read_mbin, scale_mbin_file_inplace
from sonoplan_adapter.validate_outputs import discover_punctual_output_specs


def _rect_snapshot(*, w: float = 20.0, d: float = 12.0, h: float = 6.0) -> dict:
    return {
        "schemaVersion": "1.0",
        "rooms": [
            {
                "id": "r1",
                "floorContour": [
                    {"x": 0, "y": 0},
                    {"x": w, "y": 0},
                    {"x": w, "y": d},
                    {"x": 0, "y": d},
                    {"x": 0, "y": 0},
                ],
                "heightM": {"value": h, "unit": "m"},
            }
        ],
        "sources": [
            {
                "id": "s1",
                "name": "Fan",
                "position": {"x": 2, "y": 3, "z": 1.2},
                "powerSpectrumLw": [
                    {"bandHz": 100, "level": {"value": 90, "unit": "dB"}},
                    {"bandHz": 1000, "level": {"value": 85, "unit": "dB"}},
                ],
            }
        ],
        "workplaces": [
            {
                "id": "w1",
                "name": "RM-1",
                "position": {"x": 15, "y": 8, "z": 0},
                "receiverHeightM": {"value": 1.5, "unit": "m"},
            }
        ],
    }


class ExportRevisionTests(unittest.TestCase):
    def test_compact_payload_rectangle(self) -> None:
        p = compact_export_payload(_rect_snapshot())
        self.assertTrue(p["box"]["exactRectangle"])
        self.assertAlmostEqual(p["box"]["widthM"], 20.0)
        self.assertAlmostEqual(p["box"]["depthM"], 12.0)
        self.assertAlmostEqual(p["box"]["heightM"], 6.0)
        self.assertEqual(len(p["sources"]), 1)
        self.assertEqual(len(p["workplaces"]), 1)
        self.assertAlmostEqual(p["workplaces"][0]["z"], 1.5)

    def test_write_workdir_scales_mesh(self) -> None:
        root = Path(__file__).resolve().parents[2]
        fixture = root / "fixtures" / "minimal_room" / "inputs"
        if not (fixture / "mesh.cbin").is_file():
            self.skipTest("fixture mesh missing")
        payload = compact_export_payload(_rect_snapshot(w=10, d=8, h=4))
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            meta = write_spps_workdir(
                payload=payload, out_dir=out, fixture_inputs=fixture
            )
            self.assertTrue((out / "mesh.cbin").is_file())
            self.assertTrue((out / "tetramesh.mbin").is_file())
            self.assertTrue((out / "config.xml").is_file())
            surf = read_cbin(out / "mesh.cbin")
            xs = [v[0] for v in surf.vertices]
            self.assertAlmostEqual(max(xs), 10.0, places=3)
            tetra = read_mbin(out / "tetramesh.mbin")
            self.assertEqual(len(tetra.nodes), 8)
            self.assertEqual(meta.source_count, 1)
            cfg = (out / "config.xml").read_text(encoding="utf-8")
            self.assertIn('name="Fan"', cfg)
            self.assertIn("RM-1", cfg)
            # In-place scale must preserve non-coordinate fixture bytes
            orig = (fixture / "mesh.cbin").read_bytes()
            scaled = (out / "mesh.cbin").read_bytes()
            self.assertEqual(len(orig), len(scaled))
            self.assertEqual(orig[8:10], scaled[8:10])  # node type
            self.assertEqual(orig[10:12], scaled[10:12])  # pad (not zeroed)

    def test_inplace_identity_scale_preserves_fixture_bytes(self) -> None:
        root = Path(__file__).resolve().parents[2]
        fixture = root / "fixtures" / "minimal_room" / "inputs"
        if not (fixture / "mesh.cbin").is_file():
            self.skipTest("fixture mesh missing")
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            scale_cbin_file_inplace(
                fixture / "mesh.cbin",
                out / "mesh.cbin",
                width_m=5.0,
                depth_m=5.0,
                height_m=5.0,
            )
            scale_mbin_file_inplace(
                fixture / "tetramesh.mbin",
                out / "tetramesh.mbin",
                width_m=5.0,
                depth_m=5.0,
                height_m=5.0,
            )
            self.assertEqual(
                (fixture / "mesh.cbin").read_bytes(),
                (out / "mesh.cbin").read_bytes(),
            )
            self.assertEqual(
                (fixture / "tetramesh.mbin").read_bytes(),
                (out / "tetramesh.mbin").read_bytes(),
            )

    def test_discover_punctual_specs_uses_workplace_folder(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            recp = work / "Punctual receivers" / "RM-1" / "Sound level.recp"
            recp.parent.mkdir(parents=True)
            recp.write_bytes(b"\x00\x01")
            specs = discover_punctual_output_specs(work)
            paths = [s.relative_path for s in specs if s.required]
            self.assertEqual(paths, ["Punctual receivers/RM-1/Sound level.recp"])


if __name__ == "__main__":
    unittest.main()
