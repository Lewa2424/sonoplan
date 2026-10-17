"""Unit tests for Phase 3A AABB obstacle mesher (no SPPS binary)."""

from __future__ import annotations

import struct
import tempfile
import unittest
from pathlib import Path

from sonoplan_adapter.aabb_obstacle_mesh import (
    MAT_FLOOR,
    MAT_OBSTACLE,
    MAT_WALLS,
    SolidBox,
    build_aabb_obstacle_mesh,
    write_obstacle_mesh_files,
)
from sonoplan_adapter.cbin_io import read_cbin
from sonoplan_adapter.mbin_io import read_mbin


def _tetra_volume(
    nodes: list[tuple[float, float, float]], verts: tuple[int, int, int, int]
) -> float:
    ax, ay, az = nodes[verts[0]]
    bx, by, bz = nodes[verts[1]]
    cx, cy, cz = nodes[verts[2]]
    dx, dy, dz = nodes[verts[3]]
    # V = |scalar triple product| / 6
    ab = (bx - ax, by - ay, bz - az)
    ac = (cx - ax, cy - ay, cz - az)
    ad = (dx - ax, dy - ay, dz - az)
    cross = (
        ab[1] * ac[2] - ab[2] * ac[1],
        ab[2] * ac[0] - ab[0] * ac[2],
        ab[0] * ac[1] - ab[1] * ac[0],
    )
    return abs(cross[0] * ad[0] + cross[1] * ad[1] + cross[2] * ad[2]) / 6.0


class AabbObstacleMeshTests(unittest.TestCase):
    def test_empty_room_volume_and_materials(self) -> None:
        built = build_aabb_obstacle_mesh(
            width=10.0, depth=8.0, height=4.0, solids=[]
        )
        total_v = sum(
            _tetra_volume(
                built.tetra.nodes,
                struct.unpack_from("<4i", raw, 0),  # type: ignore[arg-type]
            )
            for raw in built.tetra.tetras
        )
        self.assertAlmostEqual(total_v, 10.0 * 8.0 * 4.0, places=3)
        mats = {f.id_mat for f in built.surface.faces}
        self.assertIn(MAT_FLOOR, mats)
        self.assertIn(MAT_WALLS, mats)
        self.assertNotIn(MAT_OBSTACLE, mats)

    def test_solid_reduces_air_volume_and_adds_obstacle_faces(self) -> None:
        solid = SolidBox(2.0, 4.0, 2.0, 3.0, 0.0, 2.0, "rack")
        built = build_aabb_obstacle_mesh(
            width=10.0, depth=8.0, height=4.0, solids=[solid]
        )
        total_v = sum(
            _tetra_volume(
                built.tetra.nodes,
                struct.unpack_from("<4i", raw, 0),  # type: ignore[arg-type]
            )
            for raw in built.tetra.tetras
        )
        expected = 10.0 * 8.0 * 4.0 - (2.0 * 1.0 * 2.0)
        self.assertAlmostEqual(total_v, expected, places=2)
        self.assertGreater(built.solid_cell_count, 0)
        obstacle_faces = [f for f in built.surface.faces if f.id_mat == MAT_OBSTACLE]
        self.assertGreater(len(obstacle_faces), 0)

    def test_neighbor_symmetry(self) -> None:
        built = build_aabb_obstacle_mesh(
            width=5.0,
            depth=4.0,
            height=3.0,
            solids=[SolidBox(1.0, 2.0, 1.0, 2.5, 0.0, 2.0)],
        )
        for ti, raw in enumerate(built.tetra.tetras):
            off = 20  # skip 4 verts + idVolume
            for fi in range(4):
                _a, _b, _c, marker, neigh = struct.unpack_from("<5i", raw, off)
                off += 20
                if neigh < 0:
                    self.assertEqual(neigh, -2)
                    self.assertGreaterEqual(marker, 0)
                    continue
                self.assertEqual(marker, -1)
                other = built.tetra.tetras[neigh]
                o_off = 20
                found = False
                for ofi in range(4):
                    _oa, _ob, _oc, om, on = struct.unpack_from("<5i", other, o_off)
                    o_off += 20
                    if on == ti:
                        found = True
                        self.assertEqual(om, -1)
                        break
                self.assertTrue(found, f"tetra {ti} face {fi} neighbor not mutual")

    def test_write_roundtrip_readable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            built = write_obstacle_mesh_files(
                out_cbin=out / "mesh.cbin",
                out_mbin=out / "tetramesh.mbin",
                width=6.0,
                depth=5.0,
                height=3.0,
                solids=[SolidBox(1.0, 1.5, 0.0, 3.0, 0.0, 2.5, "partition")],
            )
            surf = read_cbin(out / "mesh.cbin")
            tetra = read_mbin(out / "tetramesh.mbin")
            self.assertEqual(len(surf.vertices), len(built.surface.vertices))
            self.assertEqual(len(surf.faces), len(built.surface.faces))
            self.assertEqual(len(tetra.nodes), len(built.tetra.nodes))
            self.assertEqual(len(tetra.tetras), len(built.tetra.tetras))
            # Every marker on a boundary tetra face points into surface faces.
            for raw in tetra.tetras:
                off = 20
                for _ in range(4):
                    _a, _b, _c, marker, neigh = struct.unpack_from("<5i", raw, off)
                    off += 20
                    if neigh == -2:
                        self.assertGreaterEqual(marker, 0)
                        self.assertLess(marker, len(surf.faces))


if __name__ == "__main__":
    unittest.main()
