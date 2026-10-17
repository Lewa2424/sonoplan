"""ENG-006: RSBIN .csbin decode + plan grid (synthetic fixture, not invented Lp)."""

from __future__ import annotations

import math
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


def _spps_coupe(
    *, base: int, nb_rows: int, nb_cols: int, energy: dict[tuple[int, int], float]
) -> list[tuple[int, int, int, float]]:
    """Faces in SauveRecepteursSurfaciquesCoupe order (two per cell)."""
    nvc = nb_cols + 1
    faces: list[tuple[int, int, int, float]] = []
    for row in range(nb_rows):
        for col in range(nb_cols):
            e = energy.get((row, col), 0.0)
            a = base + col + 1 + row * nvc
            b = base + col + row * nvc
            c = base + col + (row + 1) * nvc
            d = base + col + 1 + (row + 1) * nvc
            faces.append((a, b, c, e))
            faces.append((a, c, d, e))
    return faces


def _spps_nodes(
    *, b: tuple[float, float], step_u: tuple[float, float], step_v: tuple[float, float],
    nb_rows: int, nb_cols: int, z: float = 1.9,
) -> list[tuple[float, float, float]]:
    nodes = []
    for row in range(nb_rows + 1):
        for col in range(nb_cols + 1):
            nodes.append(
                (
                    b[0] + step_u[0] * row + step_v[0] * col,
                    b[1] + step_u[1] * row + step_v[1] * col,
                    z,
                )
            )
    return nodes


class MultiReceiverCoupeTests(unittest.TestCase):
    def test_plan_and_mirror_probe_decode_independently(self) -> None:
        rows, cols = 4, 3
        main_nodes = _spps_nodes(
            b=(0.0, 0.0), step_u=(1.0, 0.0), step_v=(0.0, 1.0), nb_rows=rows, nb_cols=cols
        )
        # Mirror: B at (4,3), BC along −X, BA along −Y.
        probe_nodes = _spps_nodes(
            b=(4.0, 3.0), step_u=(-1.0, 0.0), step_v=(0.0, -1.0), nb_rows=rows, nb_cols=cols
        )
        main_faces = _spps_coupe(base=0, nb_rows=rows, nb_cols=cols, energy={(3, 2): 1e-2})
        probe_faces = _spps_coupe(
            base=len(main_nodes), nb_rows=rows, nb_cols=cols, energy={(0, 0): 1e-2}
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rs_cut.csbin"
            write_synthetic_csbin(
                path,
                nodes=main_nodes + probe_nodes,
                faces=main_faces,
                extra_receivers=((7002, "probe_coupe_mirror", probe_faces),),
            )
            decoded = read_surface_csbin(path)
        self.assertEqual(decoded.receiver_name, "plan_coupe")
        self.assertEqual(len(decoded.faces), rows * cols * 2)
        receivers = decoded.receivers or []
        self.assertEqual([r.xml_index for r in receivers], [7001, 7002])
        for rec in receivers:
            grid = rec.grid
            assert grid is not None
            self.assertEqual((grid["nx"], grid["ny"]), (rows, cols))
            filled = [k for k, v in enumerate(grid["lpDb"]) if v is not None]
            # Main row 3/col 2 and mirror row 0/col 0 are the same world cell.
            self.assertEqual(filled, [2 * rows + 3])
        self.assertEqual(
            receivers[0].layout,
            {
                "nbRows": rows,
                "nbCols": cols,
                "energizedCells": 1,
                "energizedRowMin": 3,
                "energizedRowMax": 3,
                "energizedColMin": 2,
                "energizedColMax": 2,
            },
        )
        assert receivers[1].layout is not None
        self.assertEqual(receivers[1].layout["energizedRowMax"], 0)
        self.assertEqual(decoded.grid, receivers[0].grid)


class CoupeSpanGateTests(unittest.TestCase):
    def _manifest_for(self, energy: dict[tuple[int, int], float]) -> dict:
        rows, cols = 9, 6
        nodes = _spps_nodes(
            b=(0.0, 0.0), step_u=(1.0, 0.0), step_v=(0.0, 1.0), nb_rows=rows, nb_cols=cols
        )
        faces = _spps_coupe(base=0, nb_rows=rows, nb_cols=cols, energy=energy)
        punctual = [{"receiverId": "wp", "lpDbGlobal": 90.0}]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rs_cut.csbin"
            write_synthetic_csbin(path, nodes=nodes, faces=faces)
            surface = read_surface_csbin(path).to_dict()
        return build_result_manifest(
            job_id="j",
            revision_id="r",
            snapshot_hash="0" * 64,
            attempt=CalculationAttempt(ok=True, work_dir="w"),
            decoded={"ok": True, "punctual": punctual, "surface": surface},
        )

    def test_corner_only_patch_is_not_published(self) -> None:
        # Shape of job 6aed4c64: dense patch from the B corner, far edges empty
        # (65% fill passes the sparse gate; 78%×83% span does not).
        man = self._manifest_for(
            {(r, c): 1e-2 for r in range(7) for c in range(5)}
        )
        self.assertFalse(man["mapAvailable"])
        self.assertIsNone(man["grid"])
        self.assertIn("covers only", man["mapDeferredReason"])
        # Raw grid stays in the manifest for diagnosis, not as the plan map.
        self.assertIsNotNone(man["surface"]["grid"])

    def test_full_coverage_is_published(self) -> None:
        man = self._manifest_for(
            {(r, c): 1e-2 for r in range(9) for c in range(6)}
        )
        self.assertTrue(man["mapAvailable"])
        self.assertIsNotNone(man["grid"])


class PerBandCutATests(unittest.TestCase):
    """output_recs_byfreq=1: recepteurss/<f> Hz/rs_cut.csbin → grid.laDb."""

    ROWS, COLS = 3, 2

    def _write(self, path: Path, energy: dict[tuple[int, int], float]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        nodes = _spps_nodes(
            b=(0.0, 0.0), step_u=(1.0, 0.0), step_v=(0.0, 1.0),
            nb_rows=self.ROWS, nb_cols=self.COLS,
        )
        write_synthetic_csbin(
            path,
            nodes=nodes,
            faces=_spps_coupe(base=0, nb_rows=self.ROWS, nb_cols=self.COLS, energy=energy),
        )

    def _decode(self, bands: dict[int, dict[tuple[int, int], float]], global_e=None):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            total: dict[tuple[int, int], float] = {}
            for hz, en in bands.items():
                self._write(work / "recepteurss" / f"{hz} Hz" / "rs_cut.csbin", en)
                for k, v in en.items():
                    total[k] = total.get(k, 0.0) + v
            self._write(
                work / "recepteurss" / "Global" / "rs_cut.csbin",
                total if global_e is None else global_e,
            )
            return decode_spps_workdir(work).surface

    def test_a_weighted_once_per_band_then_energy_sum(self) -> None:
        cells = {(r, c): 1e-2 for r in range(self.ROWS) for c in range(self.COLS)}
        surface = self._decode({125: cells, 1000: cells})
        assert surface is not None
        self.assertTrue(surface["aWeighting"]["available"], surface["aWeighting"])
        grid = surface["grid"]
        self.assertEqual(grid["laBandsHz"], [125, 1000])
        # Each cell: two triangles → 2e-2 per band. LA = L1000 + 10·lg(1 + 10^−1.61).
        l1000 = 10 * math.log10(2e-2 / (20e-6) ** 2)
        for la, lz in zip(grid["laDb"], grid["lpDb"]):
            self.assertAlmostEqual(la, l1000 + 10 * math.log10(1 + 10 ** -1.61), places=4)
            self.assertAlmostEqual(lz, l1000 + 10 * math.log10(2), places=4)

    def test_empty_cell_stays_null_not_zero_db(self) -> None:
        cells = {(r, c): 1e-2 for r in range(self.ROWS) for c in range(self.COLS)}
        cells.pop((0, 0))
        surface = self._decode({1000: cells, 4000: cells})
        assert surface is not None
        self.assertTrue(surface["aWeighting"]["available"])
        self.assertEqual(sum(v is None for v in surface["grid"]["laDb"]), 1)

    def test_band_files_inconsistent_with_global_are_not_used(self) -> None:
        cells = {(r, c): 1e-2 for r in range(self.ROWS) for c in range(self.COLS)}
        doubled = {k: v * 4 for k, v in cells.items()}
        surface = self._decode({1000: cells}, global_e=doubled)
        assert surface is not None
        self.assertFalse(surface["aWeighting"]["available"])
        self.assertIn("deviates", surface["aWeighting"]["reason"])
        self.assertNotIn("laDb", surface["grid"])

    def test_without_band_files_no_la_grid(self) -> None:
        cells = {(r, c): 1e-2 for r in range(self.ROWS) for c in range(self.COLS)}
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            self._write(work / "recepteurss" / "Global" / "rs_cut.csbin", cells)
            surface = decode_spps_workdir(work).surface
        assert surface is not None
        self.assertFalse(surface["aWeighting"]["available"])
        self.assertNotIn("laDb", surface["grid"])


if __name__ == "__main__":
    unittest.main()
