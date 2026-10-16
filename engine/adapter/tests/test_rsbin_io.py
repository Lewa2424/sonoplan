"""ENG-006: RSBIN .csbin decode + plan grid (synthetic fixture, not invented Lp)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sonoplan_adapter.job_run import CalculationAttempt, build_result_manifest
from sonoplan_adapter.results import decode_spps_workdir
from sonoplan_adapter.rsbin_io import read_surface_csbin, write_synthetic_csbin


class RsbinIoTests(unittest.TestCase):
    def test_roundtrip_synthetic_and_grid(self) -> None:
        # 2×2 cells → 4 quads as 8 triangles, non-zero energy on some faces
        nodes = [
            (0.0, 0.0, 1.5),
            (1.0, 0.0, 1.5),
            (2.0, 0.0, 1.5),
            (0.0, 1.0, 1.5),
            (1.0, 1.0, 1.5),
            (2.0, 1.0, 1.5),
            (0.0, 2.0, 1.5),
            (1.0, 2.0, 1.5),
            (2.0, 2.0, 1.5),
        ]
        # energy high enough for finite Lp
        e = 1e-2
        faces = [
            (0, 1, 4, e),
            (0, 4, 3, e),
            (1, 2, 5, e * 2),
            (1, 5, 4, e * 2),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rs_cut.csbin"
            write_synthetic_csbin(path, nodes=nodes, faces=faces)
            decoded = read_surface_csbin(path)
            self.assertEqual(len(decoded.nodes), 9)
            self.assertEqual(len(decoded.faces), 4)
            self.assertIsNotNone(decoded.grid)
            assert decoded.grid is not None
            self.assertTrue(any(v is not None for v in decoded.grid["lpDb"]))
            self.assertGreater(decoded.grid["nx"], 0)

    def test_coupe_two_triangles_per_cell_no_stripe_rows(self) -> None:
        """SPPS coupe writes 2 triangles/cell; lattice grid must not stripe."""
        # 3×3 nodes → 2×2 cells; each cell = 2 triangles (centroids mid-cell)
        nodes = [
            (0.0, 0.0, 1.5),
            (1.0, 0.0, 1.5),
            (2.0, 0.0, 1.5),
            (0.0, 1.0, 1.5),
            (1.0, 1.0, 1.5),
            (2.0, 1.0, 1.5),
            (0.0, 2.0, 1.5),
            (1.0, 2.0, 1.5),
            (2.0, 2.0, 1.5),
        ]
        e = 1e-2
        faces = [
            # cell (0,0)
            (0, 1, 4, e),
            (0, 4, 3, e),
            # cell (1,0)
            (1, 2, 5, e),
            (1, 5, 4, e),
            # cell (0,1)
            (3, 4, 7, e),
            (3, 7, 6, e),
            # cell (1,1)
            (4, 5, 8, e),
            (4, 8, 7, e),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rs_cut.csbin"
            write_synthetic_csbin(path, nodes=nodes, faces=faces)
            grid = read_surface_csbin(path).grid
            self.assertIsNotNone(grid)
            assert grid is not None
            self.assertEqual(grid["nx"], 2)
            self.assertEqual(grid["ny"], 2)
            self.assertEqual(grid.get("source"), "rsbin_coupe_lattice")
            lp = grid["lpDb"]
            self.assertEqual(len(lp), 4)
            self.assertTrue(all(v is not None for v in lp))

    def test_manifest_map_available_from_csbin(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            (work / "recepteurss").mkdir()
            write_synthetic_csbin(
                work / "recepteurss" / "rs_cut.csbin",
                nodes=[
                    (0.0, 0.0, 1.5),
                    (1.0, 0.0, 1.5),
                    (0.0, 1.0, 1.5),
                ],
                faces=[(0, 1, 2, 1e-2)],
            )
            # No punctual — decode_spps_workdir.ok may be False, but surface present
            decoded = decode_spps_workdir(work)
            self.assertIsNotNone(decoded.surface)
            attempt = CalculationAttempt(
                ok=True,
                work_dir=str(work),
                artifact_paths=["recepteurss/rs_cut.csbin"],
            )
            man = build_result_manifest(
                job_id="j",
                revision_id="r",
                snapshot_hash="0" * 64,
                attempt=attempt,
                decoded=decoded.to_dict(),
            )
            self.assertTrue(man["mapAvailable"])
            self.assertIsNotNone(man["grid"])
            self.assertIsNone(man.get("mapDeferredReason"))


if __name__ == "__main__":
    unittest.main()
