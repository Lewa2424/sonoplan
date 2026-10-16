"""I-Simpa formatRSBIN (*.csbin) reader — surface / cutting-plane receivers.

Port of ``lib_interface/.../rsbin.cpp`` ImportBIN (VERSION=3).
Energy on disk is p²-homogeneous (same family as .recp); Lp via energy_to_lp.
"""

from __future__ import annotations

import math
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .results import P0_INV_PREF2

RSBIN_VERSION = 3
# Layout matching typical MSVC packing used by I-Simpa RSBIN ExportBIN.
_NODE_SIZE = 12  # 3×float
_FACE_SIZE = 16  # 3×int32 indices + int32 nbRecords
_FACE_VALUE_SIZE = 8  # uint16 timeStep + pad + float energy
_REC_S_SIZE = 4 + 4 + 255 + 1  # pad name to 256-ish alignment (263→264)


@dataclass(frozen=True)
class SurfaceFaceEnergy:
    a: int
    b: int
    c: int
    energy_sum: float
    lp_db: float | None


@dataclass
class SurfaceReceiverBlock:
    """One recepteur surfacique inside the RSBIN file (faces share ``nodes``)."""

    xml_index: int
    name: str
    faces: list[SurfaceFaceEnergy]
    grid: dict[str, Any] | None
    layout: dict[str, Any] | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "xmlIndex": self.xml_index,
            "name": self.name,
            "faceCount": len(self.faces),
            "grid": self.grid,
            "layout": self.layout,
        }


@dataclass
class SurfaceCsbin:
    """Decoded surface / coupe receiver file.

    ``faces`` / ``grid`` / ``receiver_name`` describe the first receiver
    (export writes the plan coupe first); ``receivers`` lists all of them.
    """

    path: str
    record_type: int
    time_step_s: float
    nb_time_step: int
    nodes: list[tuple[float, float, float]]
    faces: list[SurfaceFaceEnergy]
    receiver_name: str
    # Regular grid for plan heatmap (may be empty if faces cannot be binned).
    grid: dict[str, Any] | None = None
    receivers: list[SurfaceReceiverBlock] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "recordType": self.record_type,
            "timeStepS": self.time_step_s,
            "nbTimeStep": self.nb_time_step,
            "receiverName": self.receiver_name,
            "nodeCount": len(self.nodes),
            "faceCount": len(self.faces),
            "grid": self.grid,
            "receivers": [r.to_dict() for r in (self.receivers or [])],
            "notes": [
                "RSBIN energy is p^2-homogeneous; Lp after energy sum.",
                "Zero face energy → lpDb=null (not 0 dB).",
            ],
        }


class CsbinDecodeError(ValueError):
    """Surface .csbin present but not a valid RSBIN payload."""


def energy_sum_to_lp(energy: float) -> float | None:
    if energy <= 0 or not math.isfinite(energy):
        return None
    return 10.0 * math.log10(energy * P0_INV_PREF2)


_HEADER_FMT = "<iIIIIIiiifi"
_HEADER_SIZE = struct.calcsize(_HEADER_FMT)


def write_synthetic_csbin(
    path: Path,
    *,
    nodes: list[tuple[float, float, float]],
    faces: list[tuple[int, int, int, float]],
    receiver_name: str = "plan_coupe",
    time_step_s: float = 5e-4,
    extra_receivers: tuple[tuple[int, str, list[tuple[int, int, int, float]]], ...] = (),
) -> None:
    """Write a minimal VERSION=3 RSBIN for unit tests (not from SPPS).

    Zero-energy faces get ``nbRecords=0`` like SPPS.
    """
    receivers = ((7001, receiver_name, faces), *extra_receivers)
    buf = bytearray()
    buf += struct.pack(
        _HEADER_FMT,
        RSBIN_VERSION,
        _HEADER_SIZE,
        _NODE_SIZE,
        _REC_S_SIZE,
        _FACE_SIZE,
        _FACE_VALUE_SIZE,
        len(nodes),
        len(receivers),
        1,  # nbTimeStep
        float(time_step_s),
        0,  # SPL_STANDART
    )
    for x, y, z in nodes:
        buf += struct.pack("<fff", float(x), float(y), float(z))
    for xml_index, rec_name, rec_faces in receivers:
        name = rec_name.encode("ascii", errors="replace")[:255]
        name_field = bytearray(_REC_S_SIZE - 8)
        name_field[: len(name)] = name
        buf += struct.pack("<ii", int(xml_index), len(rec_faces))
        buf += bytes(name_field)
        for a, b, c, energy in rec_faces:
            if energy > 0:
                buf += struct.pack("<iiii", int(a), int(b), int(c), 1)
                buf += struct.pack("<Hxxf", 0, float(energy))
            else:
                buf += struct.pack("<iiii", int(a), int(b), int(c), 0)
    path.write_bytes(bytes(buf))


def read_surface_csbin(path: Path | str) -> SurfaceCsbin:
    p = Path(path)
    data = p.read_bytes()
    if len(data) < 44:
        raise CsbinDecodeError("csbin too short for header")
    (
        format_version,
        hdr_len,
        node_len,
        rec_len,
        face_len,
        face_val_len,
        quant_nodes,
        quant_rs,
        nb_time_step,
        time_step,
        record_type,
    ) = struct.unpack_from(_HEADER_FMT, data, 0)
    if format_version not in (RSBIN_VERSION, 2, 1):
        raise CsbinDecodeError(f"unsupported rsbin version {format_version}")
    off = hdr_len if hdr_len >= _HEADER_SIZE else _HEADER_SIZE
    nodes: list[tuple[float, float, float]] = []
    for _ in range(quant_nodes):
        if off + node_len > len(data):
            raise CsbinDecodeError("truncated nodes")
        x, y, z = struct.unpack_from("<fff", data, off)
        nodes.append((x, y, z))
        off += node_len

    blocks: list[SurfaceReceiverBlock] = []
    for _rs in range(quant_rs):
        if off + rec_len > len(data):
            raise CsbinDecodeError("truncated recepteurS")
        xml_index, quant_faces = struct.unpack_from("<ii", data, off)
        raw_name = data[off + 8 : off + rec_len]
        receiver_name = raw_name.split(b"\x00", 1)[0].decode(
            "ascii", errors="replace"
        )
        off += rec_len
        faces_out: list[SurfaceFaceEnergy] = []
        for _f in range(quant_faces):
            if off + face_len > len(data):
                raise CsbinDecodeError("truncated face")
            a, b, c, nb_rec = struct.unpack_from("<iiii", data, off)
            off += face_len
            energy_sum = 0.0
            for _t in range(nb_rec):
                if off + face_val_len > len(data):
                    raise CsbinDecodeError("truncated faceValue")
                # timeStep uint16 at 0; energy float at end-4
                energy = struct.unpack_from("<f", data, off + face_val_len - 4)[0]
                energy_sum += float(energy)
                off += face_val_len
            faces_out.append(
                SurfaceFaceEnergy(
                    a=a,
                    b=b,
                    c=c,
                    energy_sum=energy_sum,
                    lp_db=energy_sum_to_lp(energy_sum),
                )
            )
        blocks.append(
            SurfaceReceiverBlock(
                xml_index=int(xml_index),
                name=receiver_name or "surface",
                faces=faces_out,
                grid=_faces_to_grid(nodes, faces_out),
                layout=_coupe_index_layout(faces_out),
            )
        )

    main = blocks[0] if blocks else None
    return SurfaceCsbin(
        path=str(p),
        record_type=int(record_type),
        time_step_s=float(time_step),
        nb_time_step=int(nb_time_step),
        nodes=nodes,
        faces=list(main.faces) if main else [],
        receiver_name=main.name if main else "surface",
        grid=main.grid if main else None,
        receivers=blocks,
    )


def _coupe_index_layout(faces: list[SurfaceFaceEnergy]) -> dict[str, Any] | None:
    """Energized cell extents in SPPS write order (no node coordinates used).

    SauveRecepteursSurfaciquesCoupe writes face ``2*(col + row*nbcols)`` with
    vertex ``b = base + col + row*(nbcols+1)`` and ``c = b + nbcols + 1``.
    Cross-checks the coordinate-based grid against the raw SPPS cell index.
    """
    if len(faces) < 2 or len(faces) % 2:
        return None
    nb_cols = faces[0].c - faces[0].b - 1
    if nb_cols < 1 or (len(faces) // 2) % nb_cols:
        return None
    nb_rows = (len(faces) // 2) // nb_cols
    rows: list[int] = []
    cols: list[int] = []
    for k in range(0, len(faces), 2):
        if faces[k].energy_sum > 0 and math.isfinite(faces[k].energy_sum):
            cell = k // 2
            rows.append(cell // nb_cols)
            cols.append(cell % nb_cols)
    if not rows:
        return {"nbRows": nb_rows, "nbCols": nb_cols, "energizedCells": 0}
    return {
        "nbRows": nb_rows,
        "nbCols": nb_cols,
        "energizedCells": len(rows),
        "energizedRowMin": min(rows),
        "energizedRowMax": max(rows),
        "energizedColMin": min(cols),
        "energizedColMax": max(cols),
    }


def grid_energy_span(grid: dict[str, Any]) -> tuple[float, float]:
    """Fraction of the grid width/height covered by filled cells (bbox)."""
    nx = int(grid.get("nx") or 0)
    ny = int(grid.get("ny") or 0)
    lp = list(grid.get("lpDb") or [])
    if nx < 1 or ny < 1 or len(lp) < nx * ny:
        return 0.0, 0.0
    xs = [k % nx for k in range(nx * ny) if lp[k] is not None]
    ys = [k // nx for k in range(nx * ny) if lp[k] is not None]
    if not xs:
        return 0.0, 0.0
    return (max(xs) - min(xs) + 1) / nx, (max(ys) - min(ys) + 1) / ny


def _faces_to_grid(
    nodes: list[tuple[float, float, float]],
    faces: list[SurfaceFaceEnergy],
) -> dict[str, Any] | None:
    """Bin face energy into a regular XY grid for plan heatmap.

    Coupe RSBIN stores each cell as **two triangles**. Centroid-only spacing
    is ~½–⅓ of the true cell → empty stripe rows in the plan. Prefer the
    **node lattice** (unique X/Y of vertices) as the cell size.
    """
    if not faces or not nodes:
        return None
    centroids: list[tuple[float, float, float, float]] = []
    zs: list[float] = []
    for f in faces:
        try:
            pa, pb, pc = nodes[f.a], nodes[f.b], nodes[f.c]
        except IndexError:
            continue
        if f.energy_sum <= 0:
            continue
        cx = (pa[0] + pb[0] + pc[0]) / 3.0
        cy = (pa[1] + pb[1] + pc[1]) / 3.0
        cz = (pa[2] + pb[2] + pc[2]) / 3.0
        zs.append(cz)
        centroids.append((cx, cy, f.energy_sum, cz))
    if not centroids:
        return None

    # Node lattice = true coupe cell pitch (not triangle-centroid pitch).
    # Several receivers share one node table — use only this receiver's nodes.
    own = [
        nodes[i]
        for i in sorted({i for f in faces for i in (f.a, f.b, f.c)})
        if 0 <= i < len(nodes)
    ]
    node_xs = sorted({round(n[0], 5) for n in own})
    node_ys = sorted({round(n[1], 5) for n in own})
    use_lattice = len(node_xs) >= 2 and len(node_ys) >= 2
    if use_lattice:
        dxs = [node_xs[i + 1] - node_xs[i] for i in range(len(node_xs) - 1)]
        dys = [node_ys[i + 1] - node_ys[i] for i in range(len(node_ys) - 1)]
        cell_x = max(sorted(dxs)[len(dxs) // 2], 1e-4)
        cell_y = max(sorted(dys)[len(dys) // 2], 1e-4)
        min_x, min_y = node_xs[0], node_ys[0]
        nx = len(node_xs) - 1
        ny = len(node_ys) - 1
        source = "rsbin_coupe_lattice"
    else:
        xs = [c[0] for c in centroids]
        ys = [c[1] for c in centroids]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        span_x = max(max_x - min_x, 1e-3)
        span_y = max(max_y - min_y, 1e-3)
        uniq_x = sorted({round(x, 4) for x in xs})
        uniq_y = sorted({round(y, 4) for y in ys})
        dxs = [
            uniq_x[i + 1] - uniq_x[i]
            for i in range(len(uniq_x) - 1)
            if uniq_x[i + 1] > uniq_x[i]
        ]
        dys = [
            uniq_y[i + 1] - uniq_y[i]
            for i in range(len(uniq_y) - 1)
            if uniq_y[i + 1] > uniq_y[i]
        ]
        # Prefer larger median so triangle-pair half-steps do not stripe.
        cell = 0.5
        if dxs:
            cell = max(cell, sorted(dxs)[len(dxs) // 2])
        if dys:
            cell = max(cell, sorted(dys)[len(dys) // 2])
        cell = max(min(cell, 5.0), 0.05)
        cell_x = cell_y = cell
        nx = max(1, int(math.ceil(span_x / cell_x)))
        ny = max(1, int(math.ceil(span_y / cell_y)))
        source = "rsbin_face_centroids"

    while nx * ny > 80_000 and (cell_x < 5.0 or cell_y < 5.0):
        cell_x = min(cell_x * 1.5, 5.0)
        cell_y = min(cell_y * 1.5, 5.0)
        if use_lattice:
            nx = max(1, int(math.ceil((node_xs[-1] - node_xs[0]) / cell_x)))
            ny = max(1, int(math.ceil((node_ys[-1] - node_ys[0]) / cell_y)))
        else:
            nx = max(1, int(math.ceil(span_x / cell_x)))
            ny = max(1, int(math.ceil(span_y / cell_y)))

    energy = [0.0] * (nx * ny)
    counts = [0] * (nx * ny)
    for cx, cy, e, _cz in centroids:
        i = min(nx - 1, max(0, int((cx - min_x) / cell_x)))
        j = min(ny - 1, max(0, int((cy - min_y) / cell_y)))
        idx = j * nx + i
        energy[idx] += e
        counts[idx] += 1
    lp_db: list[float | None] = []
    for idx in range(nx * ny):
        if counts[idx] == 0:
            lp_db.append(None)
        else:
            lp_db.append(energy_sum_to_lp(energy[idx]))
    z_m = sum(zs) / len(zs) if zs else 1.5
    if not any(v is not None for v in lp_db):
        return None
    return {
        "originX": min_x,
        "originY": min_y,
        "cellSizeM": cell_x,
        "cellSizeYM": cell_y,
        "nx": nx,
        "ny": ny,
        "zM": z_m,
        "lpDb": lp_db,
        "quantity": "Lp_dB",
        "unit": "dB",
        "source": source,
    }
