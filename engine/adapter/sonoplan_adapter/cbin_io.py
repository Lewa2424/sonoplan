"""Read/write I-Simpa SPPS surface mesh (*.cbin) — subset of formatCoreBIN."""

from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path

DEFAULT_MAJOR = 1
DEFAULT_MINOR = 0
NODE_VERTICES = 0
NODE_GROUP = 1

@dataclass(frozen=True)
class Face:
    a: int
    b: int
    c: int
    id_mat: int = 0
    id_rs: int = -1
    id_en: int = -1


@dataclass
class SurfaceMesh:
    vertices: list[tuple[float, float, float]]
    faces: list[Face]


def read_cbin(path: Path) -> SurfaceMesh:
    data = path.read_bytes()
    maj, minor = struct.unpack_from("<II", data, 0)
    if maj != DEFAULT_MAJOR or minor != DEFAULT_MINOR:
        raise ValueError(f"unsupported cbin version {maj}.{minor}")
    off = 8
    vertices: list[tuple[float, float, float]] = []
    faces: list[Face] = []
    next_brother = 1
    while next_brother != 0 and off + 12 <= len(data):
        # bShort nodeType, bShort pad, bLong firstSon, bLong nextBrother (12 bytes)
        node_type, _pad, _first_son, next_brother = struct.unpack_from(
            "<HHII", data, off
        )
        off += 12
        if node_type == NODE_VERTICES:
            (n_vert,) = struct.unpack_from("<I", data, off)
            off += 4
            for _ in range(n_vert):
                x, y, z = struct.unpack_from("<fff", data, off)
                vertices.append((x, y, z))
                off += 12
        elif node_type == NODE_GROUP:
            off += 255  # groupName
            off += 1  # null
            (n_face,) = struct.unpack_from("<I", data, off)
            off += 4
            for _ in range(n_face):
                a, b, c, id_mat, id_rs, id_en = struct.unpack_from(
                    "<IIIIii", data, off
                )
                faces.append(Face(a, b, c, id_mat, id_rs, id_en))
                off += 20
        else:
            raise ValueError(f"unknown cbin node type {node_type}")
        if next_brother != 0:
            off = int(next_brother)
    return SurfaceMesh(vertices=vertices, faces=faces)


def write_cbin(path: Path, mesh: SurfaceMesh) -> None:
    """Export compatible with CformatBIN::ExportBIN (SPPS mesh.cbin)."""
    buf = bytearray()
    buf += struct.pack("<II", DEFAULT_MAJOR, DEFAULT_MINOR)

    # VERTICES node — 12-byte header; nextBrother = absolute offset after node
    vert_header_pos = len(buf)
    buf += struct.pack("<HHII", NODE_VERTICES, 0, 0, 0)
    buf += struct.pack("<I", len(mesh.vertices))
    for x, y, z in mesh.vertices:
        buf += struct.pack("<fff", float(x), float(y), float(z))
    after_verts = len(buf)
    struct.pack_into(
        "<HHII", buf, vert_header_pos, NODE_VERTICES, 0, 0, after_verts
    )

    # GROUP node — nextBrother=0 (last)
    group_header_pos = len(buf)
    buf += struct.pack("<HHII", NODE_GROUP, 0, 0, 0)
    buf += b"\x00" * 255
    buf += b"\x00"
    buf += struct.pack("<I", len(mesh.faces))
    for f in mesh.faces:
        buf += struct.pack(
            "<IIIIii",
            int(f.a),
            int(f.b),
            int(f.c),
            int(f.id_mat),
            int(f.id_rs),
            int(f.id_en),
        )
    struct.pack_into("<HHII", buf, group_header_pos, NODE_GROUP, 0, 0, 0)

    path.write_bytes(bytes(buf))


def scale_mesh_to_box(
    mesh: SurfaceMesh,
    *,
    width_m: float,
    depth_m: float,
    height_m: float,
    ref_size: float = 5.0,
) -> SurfaceMesh:
    """Scale a reference cube mesh spanning [0,ref]^3 into [0,W]×[0,D]×[0,H]."""
    sx = width_m / ref_size
    sy = depth_m / ref_size
    sz = height_m / ref_size
    verts = [(x * sx, y * sy, z * sz) for x, y, z in mesh.vertices]
    return SurfaceMesh(vertices=verts, faces=list(mesh.faces))


def scale_cbin_file_inplace(
    src: Path,
    dst: Path,
    *,
    width_m: float,
    depth_m: float,
    height_m: float,
    ref_size: float = 5.0,
) -> SurfaceMesh:
    """Scale vertex floats in-place; preserve official cbin layout/padding.

    ``write_cbin`` zeros uninitialized pad/groupName bytes that the I-Simpa
    cube fixture still carries. SPPS loads that rewritten surface, then can
    SIGSEGV on tetramesh — keep the binary shell byte-identical except coords.
    """
    data = bytearray(src.read_bytes())
    maj, minor = struct.unpack_from("<II", data, 0)
    if maj != DEFAULT_MAJOR or minor != DEFAULT_MINOR:
        raise ValueError(f"unsupported cbin version {maj}.{minor}")
    sx = width_m / ref_size
    sy = depth_m / ref_size
    sz = height_m / ref_size
    vertices: list[tuple[float, float, float]] = []
    faces: list[Face] = []
    off = 8
    next_brother = 1
    while next_brother != 0 and off + 12 <= len(data):
        node_type, _pad, _first_son, next_brother = struct.unpack_from(
            "<HHII", data, off
        )
        off += 12
        if node_type == NODE_VERTICES:
            (n_vert,) = struct.unpack_from("<I", data, off)
            off += 4
            for _ in range(n_vert):
                x, y, z = struct.unpack_from("<fff", data, off)
                nx, ny, nz = x * sx, y * sy, z * sz
                struct.pack_into("<fff", data, off, nx, ny, nz)
                vertices.append((nx, ny, nz))
                off += 12
        elif node_type == NODE_GROUP:
            off += 255  # groupName (preserve bytes)
            off += 1
            (n_face,) = struct.unpack_from("<I", data, off)
            off += 4
            for _ in range(n_face):
                a, b, c, id_mat, id_rs, id_en = struct.unpack_from(
                    "<IIIIii", data, off
                )
                faces.append(Face(a, b, c, id_mat, id_rs, id_en))
                off += 20
        else:
            raise ValueError(f"unknown cbin node type {node_type}")
        if next_brother != 0:
            off = int(next_brother)
    dst.write_bytes(bytes(data))
    return SurfaceMesh(vertices=vertices, faces=faces)
