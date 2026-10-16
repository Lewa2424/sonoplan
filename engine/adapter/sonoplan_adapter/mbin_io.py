"""Read/write I-Simpa tetramesh (*.mbin / CMBIN) — scale nodes for box rooms."""

from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path


@dataclass
class TetraMesh:
    nodes: list[tuple[float, float, float]]
    # Opaque per-tetra binary payload after the 4 vertex indices + idVolume
    # (4 faces × (3 verts + marker + neighbor) as int32) — preserved on scale.
    tetras: list[bytes]


def read_mbin(path: Path) -> TetraMesh:
    data = path.read_bytes()
    n_tetra, n_nodes = struct.unpack_from("<II", data, 0)
    off = 8
    nodes: list[tuple[float, float, float]] = []
    for _ in range(n_nodes):
        x, y, z = struct.unpack_from("<fff", data, off)
        nodes.append((x, y, z))
        off += 12
    # Each tetra: 4×int32 verts + int32 idVolume + 4×(3×int32 + 2×int32) faces
    tetra_bytes = 4 * 4 + 4 + 4 * (3 * 4 + 4 + 4)
    tetras: list[bytes] = []
    for _ in range(n_tetra):
        raw = data[off : off + tetra_bytes]
        if len(raw) != tetra_bytes:
            raise ValueError("truncated mbin tetra payload")
        # Force idVolume=0 (principal volume) — byte offset 16 after 4 verts
        patched = bytearray(raw)
        struct.pack_into("<i", patched, 16, 0)
        tetras.append(bytes(patched))
        off += tetra_bytes
    return TetraMesh(nodes=nodes, tetras=tetras)


def write_mbin(path: Path, mesh: TetraMesh) -> None:
    buf = bytearray()
    buf += struct.pack("<II", len(mesh.tetras), len(mesh.nodes))
    for x, y, z in mesh.nodes:
        buf += struct.pack("<fff", float(x), float(y), float(z))
    for raw in mesh.tetras:
        buf += raw
    path.write_bytes(bytes(buf))


def scale_tetra_to_box(
    mesh: TetraMesh,
    *,
    width_m: float,
    depth_m: float,
    height_m: float,
    ref_size: float = 5.0,
) -> TetraMesh:
    sx = width_m / ref_size
    sy = depth_m / ref_size
    sz = height_m / ref_size
    nodes = [(x * sx, y * sy, z * sz) for x, y, z in mesh.nodes]
    return TetraMesh(nodes=nodes, tetras=list(mesh.tetras))
