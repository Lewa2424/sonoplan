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
        snap = _rect_snapshot()
        snap["materials"] = [
            {
                "id": "m1",
                "catalogKey": "mineral_wool",
                "name": "Минвата",
                "version": "mvp-1",
                "estimated": True,
                "absorptionByBand": [
                    {"bandHz": 1000, "alpha": 0.7},
                    {"bandHz": 500, "alpha": 0.6},
                ],
            }
        ]
        snap["rooms"][0]["materialVersionId"] = "m1"
        snap["solids"] = [{"id": "s1", "name": "Стеллаж"}]
        p = compact_export_payload(snap)
        self.assertTrue(p["box"]["exactRectangle"])
        self.assertAlmostEqual(p["box"]["widthM"], 20.0)
        self.assertAlmostEqual(p["box"]["depthM"], 12.0)
        self.assertAlmostEqual(p["box"]["heightM"], 6.0)
        self.assertEqual(len(p["sources"]), 1)
        self.assertEqual(len(p["workplaces"]), 1)
        self.assertAlmostEqual(p["workplaces"][0]["z"], 1.5)
        self.assertAlmostEqual(p["absorptionByBand"]["1000"], 0.7)
        self.assertEqual(p["solidCount"], 1)
        self.assertIn("coupeZM", p)
        # Sources at z=1.5 → coupe must leave clearance (not coplanar blotch).
        self.assertGreaterEqual(abs(float(p["coupeZM"]) - 1.5), 0.35)

    def test_coupe_z_away_from_coplanar_sources(self) -> None:
        from sonoplan_adapter.export_revision import _coupe_z_away_from_sources

        z = _coupe_z_away_from_sources(
            preferred_z=1.5, source_zs=[1.5, 1.5], height_m=6.0
        )
        self.assertGreaterEqual(abs(z - 1.5), 0.35)

    def test_coupe_overhangs_walls_so_spps_links_all_tetras(self) -> None:
        from sonoplan_adapter.export_revision import build_config_xml

        payload = compact_export_payload(_rect_snapshot(w=20, d=12, h=6))
        coupe = build_config_xml(payload).getroot().find(
            "recepteurss/recepteur_surfacique_coupe"
        )
        assert coupe is not None
        f = {k: float(coupe.get(k) or "nan") for k in ("ay", "bx", "by", "cx")}
        # Coupe edges exactly on walls → SPPS float link test skips wall tetras.
        self.assertLess(f["bx"], 0.0)
        self.assertLess(f["by"], 0.0)
        self.assertGreater(f["ay"], 12.0)
        self.assertGreater(f["cx"], 20.0)
        self.assertLess(f["cx"] - 20.0, 0.1)

    def test_mirror_probe_coupe_has_b_in_far_corner(self) -> None:
        from sonoplan_adapter.export_revision import build_config_xml

        payload = compact_export_payload(_rect_snapshot(w=20, d=12, h=6))
        coupes = build_config_xml(payload).getroot().findall(
            "recepteurss/recepteur_surfacique_coupe"
        )
        self.assertEqual([c.get("name") for c in coupes], ["plan_coupe", "probe_coupe_mirror"])
        main, probe = coupes
        g = {k: float(probe.get(k) or "nan") for k in ("ax", "ay", "bx", "by", "cx", "cy")}
        self.assertGreater(g["bx"], 20.0)
        self.assertGreater(g["by"], 12.0)
        self.assertLess(g["cx"], 0.0)
        self.assertAlmostEqual(g["cy"], g["by"])
        self.assertAlmostEqual(g["ax"], g["bx"])
        self.assertLess(g["ay"], 0.0)
        for k in ("az", "bz", "cz", "resolution"):
            self.assertEqual(probe.get(k), main.get(k))

    def test_all_model_octaves_computed_and_cut_saved_per_band(self) -> None:
        from sonoplan_adapter.export_revision import build_config_xml

        root = build_config_xml(compact_export_payload(_rect_snapshot())).getroot()
        sim = root.find("simulation")
        assert sim is not None
        on = sorted(
            int(b.get("freq") or 0)
            for b in sim.findall("freq_enum/bfreq")
            if b.get("docalc") == "1"
        )
        self.assertEqual(on, [63, 125, 250, 500, 1000, 2000, 4000, 8000])
        self.assertEqual(sim.get("output_recs_byfreq"), "1")

    def test_coupe_resolution_halved_and_capped(self) -> None:
        from sonoplan_adapter.export_revision import MAX_COUPE_CELLS, coupe_resolution_m

        self.assertAlmostEqual(coupe_resolution_m(20, 12), 0.15)
        self.assertAlmostEqual(coupe_resolution_m(6, 4), 0.125)
        self.assertAlmostEqual(coupe_resolution_m(40, 30), 0.25)
        big = coupe_resolution_m(200, 100)
        self.assertLessEqual((200 / big) * (100 / big), MAX_COUPE_CELLS + 1e-6)

    def test_coupe_z_parity_with_web_plan_cut(self) -> None:
        """Same cases as packages/domain/src/planCut.test.ts (estimate plane)."""
        from sonoplan_adapter.export_revision import build_config_xml

        def snap(h, wps, srcs):
            s = _rect_snapshot(w=10, d=8, h=h)
            s["sources"] = [
                {"id": f"s{i}", "position": {"x": 2 + i, "y": 2, "z": z},
                 "powerSpectrumLw": [{"bandHz": 1000, "level": {"value": 90}}]}
                for i, z in enumerate(srcs)
            ]
            s["workplaces"] = [
                {"id": f"w{i}", "position": {"x": 5, "y": 5, "z": z},
                 "receiverHeightM": {"value": rh}}
                for i, (z, rh) in enumerate(wps)
            ]
            return s

        cases = [
            (6, [(0, 1.5), (0, 1.5)], [1.0], 1.5),
            (6, [(0, 1.5)], [1.5], 1.15),
            (6, [(0, 1.5)], [1.5, 1.2], 1.85),
            (6, [(0, 1.6), (1.2, 1.5)], [1.0, 1.75], 1.4),
            (6, [(0, 1.5)], [1.5, 1.15, 1.85, 0.8, 2.2], 0.25),
            (1.0, [(0, 1.5)], [0.5], 0.85),
        ]
        for h, wps, srcs, expected in cases:
            p = compact_export_payload(snap(h, wps, srcs))
            build_config_xml(p)
            self.assertAlmostEqual(p["coupeZM"], expected, places=9, msg=(h, wps, srcs))

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
            self.assertIn("recepteur_surfacique_coupe", cfg)
            self.assertIn('name="plan_coupe"', cfg)
            # SPPS joins folder+"Global/" without extra sep — trailing slash required
            self.assertIn('recepteurss_directory="recepteurss/"', cfg)
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
