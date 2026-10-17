"""AABB room + AABB solids → conforming surface (cbin) + tetra (mbin) mesh.

MVP Stage 3: UI solids are axis-aligned boxes. We carve them out of a structured
Kuhn tetrahedral grid (no TetGen binary). Full polygon / TetGen remains later.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

from .cbin_io import Face, SurfaceMesh, write_cbin
from .mbin_io import TetraMesh, write_mbin

# Material ids must match export_revision.SURFACE_MATERIAL_IDS (+ obstacle).
MAT_WALLS = 0
MAT_FLOOR = 1
MAT_CEILING = 2
MAT_OBSTACLE = 3

# Soft cap: product of cell counts; coarsen planes if exceeded.
MAX_CELLS = 40_000
# Merge cutting planes closer than this (m).
PLANE_EPS = 1e-4


@dataclass(frozen=True)
class SolidBox:
    """Axis-aligned solid in room-local coordinates (origin at AABB min)."""

    xmin: float
    xmax: float
    ymin: float
    ymax: float
    zmin: float
    zmax: float
    name: str = ""


@dataclass(frozen=True)
class MeshBuildResult:
    surface: SurfaceMesh
    tetra: TetraMesh
    air_cell_count: int
    solid_cell_count: int
    notes: tuple[str, ...]


def _uniq_sorted(values: list[float], eps: float = PLANE_EPS) -> list[float]:
    if not values:
        return []
    ordered = sorted(values)
    out = [ordered[0]]
    for v in ordered[1:]:
        if abs(v - out[-1]) > eps:
            out.append(v)
    return out


def _coarsen(planes: list[float], target: int) -> list[float]:
    if len(planes) <= target:
        return planes
    if target < 2:
        return [planes[0], planes[-1]]
    step = (len(planes) - 1) / (target - 1)
    idxs = sorted({int(round(i * step)) for i in range(target)})
    return [planes[i] for i in idxs]


def _point_in_solid(x: float, y: float, z: float, solids: list[SolidBox]) -> bool:
    for s in solids:
        if s.xmin < x < s.xmax and s.ymin < y < s.ymax and s.zmin < z < s.zmax:
            return True
    return False


def _kuhn_tets(corners: tuple[int, ...], odd: bool) -> list[tuple[int, int, int, int]]:
    """Six tetras for a cube; odd/even alternation keeps shared faces conforming."""
    v = corners
    if not odd:
        return [
            (v[0], v[1], v[3], v[7]),
            (v[0], v[1], v[7], v[5]),
            (v[1], v[2], v[3], v[7]),
            (v[1], v[2], v[7], v[6]),
            (v[1], v[5], v[7], v[6]),
            (v[0], v[4], v[5], v[7]),
        ]
    return [
        (v[0], v[1], v[2], v[6]),
        (v[0], v[2], v[3], v[6]),
        (v[0], v[1], v[6], v[5]),
        (v[0], v[4], v[5], v[6]),
        (v[0], v[3], v[7], v[6]),
        (v[0], v[4], v[6], v[7]),
    ]


def _tetra_faces(
    a: int, b: int, c: int, d: int
) -> list[tuple[int, int, int]]:
    """Face opposite each vertex — same winding as official I-Simpa cube.mbin."""
    return [
        (b, d, c),
        (c, d, a),
        (a, d, b),
        (b, c, a),
    ]


def _face_key(i: int, j: int, k: int) -> frozenset[int]:
    return frozenset((i, j, k))


def _classify_material(
    xa: float,
    ya: float,
    za: float,
    xb: float,
    yb: float,
    zb: float,
    xc: float,
    yc: float,
    zc: float,
    *,
    width: float,
    depth: float,
    height: float,
    solids: list[SolidBox],
) -> int:
    xs = (xa, xb, xc)
    ys = (ya, yb, yc)
    zs = (za, zb, zc)
    tol = max(1e-4, 1e-5 * max(width, depth, height))
    if all(abs(z) <= tol for z in zs):
        return MAT_FLOOR
    if all(abs(z - height) <= tol for z in zs):
        return MAT_CEILING
    # Obstacle: centroid on or just outside a solid AABB face, inside its XY/Z slab.
    cx = (xa + xb + xc) / 3.0
    cy = (ya + yb + yc) / 3.0
    cz = (za + zb + zc) / 3.0
    for s in solids:
        on_x = abs(cx - s.xmin) <= tol or abs(cx - s.xmax) <= tol
        on_y = abs(cy - s.ymin) <= tol or abs(cy - s.ymax) <= tol
        on_z = abs(cz - s.zmin) <= tol or abs(cz - s.zmax) <= tol
        in_yz = s.ymin - tol <= cy <= s.ymax + tol and s.zmin - tol <= cz <= s.zmax + tol
        in_xz = s.xmin - tol <= cx <= s.xmax + tol and s.zmin - tol <= cz <= s.zmax + tol
        in_xy = s.xmin - tol <= cx <= s.xmax + tol and s.ymin - tol <= cy <= s.ymax + tol
        if (on_x and in_yz) or (on_y and in_xz) or (on_z and in_xy):
            # Outer room walls share planes with solids that touch the boundary —
            # prefer room material when the face lies on the room shell.
            on_room = (
                abs(cx) <= tol
                or abs(cx - width) <= tol
                or abs(cy) <= tol
                or abs(cy - depth) <= tol
                or abs(cz) <= tol
                or abs(cz - height) <= tol
            )
            if not on_room:
                return MAT_OBSTACLE
    if all(abs(x) <= tol or abs(x - width) <= tol for x in xs) or all(
        abs(y) <= tol or abs(y - depth) <= tol for y in ys
    ):
        return MAT_WALLS
    # Internal grid faces should not appear as surface (they have two tetras).
    return MAT_WALLS


def _pack_tetra(
    verts: tuple[int, int, int, int],
    faces: list[tuple[int, int, int, int, int]],
) -> bytes:
    """4×int32 verts + int32 idVolume + 4×(3 verts + marker + neighbor)."""
    buf = bytearray()
    buf += struct.pack("<4i", *verts)
    buf += struct.pack("<i", 0)  # idVolume = principal air
    for a, b, c, marker, neigh in faces:
        buf += struct.pack("<5i", a, b, c, marker, neigh)
    return bytes(buf)


def build_aabb_obstacle_mesh(
    *,
    width: float,
    depth: float,
    height: float,
    solids: list[SolidBox],
) -> MeshBuildResult:
    """Carve AABB solids from a Kuhn grid; return SPPS-ready surface + tetra meshes."""
    if width <= 0 or depth <= 0 or height <= 0:
        raise ValueError("room dimensions must be > 0")

    xs = [0.0, width]
    ys = [0.0, depth]
    zs = [0.0, height]
    clipped: list[SolidBox] = []
    for s in solids:
        xmin = max(0.0, min(s.xmin, s.xmax))
        xmax = min(width, max(s.xmin, s.xmax))
        ymin = max(0.0, min(s.ymin, s.ymax))
        ymax = min(depth, max(s.ymin, s.ymax))
        zmin = max(0.0, min(s.zmin, s.zmax))
        zmax = min(height, max(s.zmin, s.zmax))
        if xmax - xmin < 1e-3 or ymax - ymin < 1e-3 or zmax - zmin < 1e-3:
            continue
        box = SolidBox(xmin, xmax, ymin, ymax, zmin, zmax, s.name)
        clipped.append(box)
        xs.extend([xmin, xmax])
        ys.extend([ymin, ymax])
        zs.extend([zmin, zmax])

    xs = _uniq_sorted(xs)
    ys = _uniq_sorted(ys)
    zs = _uniq_sorted(zs)

    # Coarsen if the cartesian product would explode.
    nx, ny, nz = len(xs) - 1, len(ys) - 1, len(zs) - 1
    while nx * ny * nz > MAX_CELLS and (nx > 1 or ny > 1 or nz > 1):
        # Prefer coarsening the densest axis (keep room bounds).
        counts = [("x", nx, xs), ("y", ny, ys), ("z", nz, zs)]
        counts.sort(key=lambda t: t[1], reverse=True)
        axis, n, planes = counts[0]
        new_planes = _coarsen(planes, max(2, n))
        if axis == "x":
            xs = new_planes
        elif axis == "y":
            ys = new_planes
        else:
            zs = new_planes
        nx, ny, nz = len(xs) - 1, len(ys) - 1, len(zs) - 1

    # Node grid
    node_index: dict[tuple[int, int, int], int] = {}
    nodes: list[tuple[float, float, float]] = []
    for iz, z in enumerate(zs):
        for iy, y in enumerate(ys):
            for ix, x in enumerate(xs):
                node_index[(ix, iy, iz)] = len(nodes)
                nodes.append((x, y, z))

    def corner(ix: int, iy: int, iz: int) -> int:
        return node_index[(ix, iy, iz)]

    # Cell occupancy + tetras
    tetras_verts: list[tuple[int, int, int, int]] = []
    air_cells = 0
    solid_cells = 0
    for iz in range(nz):
        for iy in range(ny):
            for ix in range(nx):
                x0, x1 = xs[ix], xs[ix + 1]
                y0, y1 = ys[iy], ys[iy + 1]
                z0, z1 = zs[iz], zs[iz + 1]
                cx = 0.5 * (x0 + x1)
                cy = 0.5 * (y0 + y1)
                cz = 0.5 * (z0 + z1)
                if _point_in_solid(cx, cy, cz, clipped):
                    solid_cells += 1
                    continue
                air_cells += 1
                corners = (
                    corner(ix, iy, iz),
                    corner(ix + 1, iy, iz),
                    corner(ix + 1, iy + 1, iz),
                    corner(ix, iy + 1, iz),
                    corner(ix, iy, iz + 1),
                    corner(ix + 1, iy, iz + 1),
                    corner(ix + 1, iy + 1, iz + 1),
                    corner(ix, iy + 1, iz + 1),
                )
                odd = (ix + iy + iz) % 2 == 1
                for t in _kuhn_tets(corners, odd):
                    tetras_verts.append(t)

    if not tetras_verts:
        raise ValueError("no air tetras left after carving solids")

    # Face adjacency: key → [(tetra_i, face_i, (a,b,c))]
    adj: dict[frozenset[int], list[tuple[int, int, tuple[int, int, int]]]] = {}
    for ti, (a, b, c, d) in enumerate(tetras_verts):
        for fi, (fa, fb, fc) in enumerate(_tetra_faces(a, b, c, d)):
            adj.setdefault(_face_key(fa, fb, fc), []).append((ti, fi, (fa, fb, fc)))

    # Surface faces + tetra face meta (marker, neighbor)
    surface_faces: list[Face] = []
    # (ti, fi) → (marker, neighbor)
    face_meta: dict[tuple[int, int], tuple[int, int]] = {}

    for key, owners in adj.items():
        if len(owners) == 2:
            (t0, f0, _), (t1, f1, _) = owners
            face_meta[(t0, f0)] = (-1, t1)
            face_meta[(t1, f1)] = (-1, t0)
            continue
        if len(owners) != 1:
            # Non-manifold — should not happen for AABB Kuhn grid
            raise ValueError(f"non-manifold face with {len(owners)} owners")
        (ti, fi, (fa, fb, fc)) = owners[0]
        xa, ya, za = nodes[fa]
        xb, yb, zb = nodes[fb]
        xc, yc, zc = nodes[fc]
        mat = _classify_material(
            xa,
            ya,
            za,
            xb,
            yb,
            zb,
            xc,
            yc,
            zc,
            width=width,
            depth=depth,
            height=height,
            solids=clipped,
        )
        marker = len(surface_faces)
        surface_faces.append(Face(fa, fb, fc, id_mat=mat, id_rs=-1, id_en=-1))
        face_meta[(ti, fi)] = (marker, -2)

    packed: list[bytes] = []
    for ti, verts in enumerate(tetras_verts):
        faces_out: list[tuple[int, int, int, int, int]] = []
        for fi, (fa, fb, fc) in enumerate(_tetra_faces(*verts)):
            marker, neigh = face_meta[(ti, fi)]
            faces_out.append((fa, fb, fc, marker, neigh))
        packed.append(_pack_tetra(verts, faces_out))

    notes = [
        (
            f"Phase 3A: AABB Kuhn mesh with {len(clipped)} solid hole(s); "
            f"{air_cells} air cells / {solid_cells} solid cells; "
            f"{len(tetras_verts)} tetras, {len(surface_faces)} surface faces "
            f"(grid {nx}×{ny}×{nz})."
        ),
        "Obstacle faces use type_surface id=3 (α from walls material by default).",
        "Not full polygon extrusion / external TetGen — axis-aligned solids only.",
    ]
    return MeshBuildResult(
        surface=SurfaceMesh(vertices=list(nodes), faces=surface_faces),
        tetra=TetraMesh(nodes=list(nodes), tetras=packed),
        air_cell_count=air_cells,
        solid_cell_count=solid_cells,
        notes=tuple(notes),
    )


def write_obstacle_mesh_files(
    *,
    out_cbin,
    out_mbin,
    width: float,
    depth: float,
    height: float,
    solids: list[SolidBox],
) -> MeshBuildResult:
    result = build_aabb_obstacle_mesh(
        width=width, depth=depth, height=height, solids=solids
    )
    write_cbin(out_cbin, result.surface)
    write_mbin(out_mbin, result.tetra)
    return result


def solid_boxes_from_payload_solids(
    solids: list[dict],
    *,
    width: float,
    depth: float,
    height: float,
) -> list[SolidBox]:
    """Parse export payload solids (room-local AABB or floorContour)."""
    out: list[SolidBox] = []
    for s in solids:
        name = str(s.get("name") or "")
        if all(k in s for k in ("xmin", "xmax", "ymin", "ymax", "zmin", "zmax")):
            out.append(
                SolidBox(
                    float(s["xmin"]),
                    float(s["xmax"]),
                    float(s["ymin"]),
                    float(s["ymax"]),
                    float(s["zmin"]),
                    float(s["zmax"]),
                    name,
                )
            )
            continue
        contour = s.get("floorContour") or []
        pts = [(float(p["x"]), float(p["y"])) for p in contour]
        if len(pts) < 3:
            continue
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        z0 = float(s.get("baseZM") or 0.0)
        h = float((s.get("heightM") or {}).get("value") or 0.0)
        if h <= 0:
            continue
        out.append(
            SolidBox(
                max(0.0, min(xs)),
                min(width, max(xs)),
                max(0.0, min(ys)),
                min(depth, max(ys)),
                max(0.0, z0),
                min(height, z0 + h),
                name,
            )
        )
    return out
