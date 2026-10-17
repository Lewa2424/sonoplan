"""I-Simpa formatRSBIN (*.csbin) reader — surface / cutting-plane receivers.

Port of ``lib_interface/.../rsbin.cpp`` ImportBIN (VERSION=3).
Cell values are energy per cell area; levels use the I-Simpa surface reference.
"""

from __future__ import annotations

import math
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any

RSBIN_VERSION = 3
SURFACE_REF = 1e-12
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
            # First receiver's grid is ``grid`` above — not repeated (manifest size).
            "receivers": [
                {**r.to_dict(), "grid": None, "gridIsTopLevel": True}
                if i == 0 and r.grid is self.grid
                else r.to_dict()
                for i, r in enumerate(self.receivers or [])
            ],
            "notes": [
                "RSBIN cell value = energy / cell area; L = 10*log10(E/1e-12) after time sum (I-Simpa surface convention).",
                "Cells placed by SPPS write order (Linux RSBIN face indices are truncated).",
                "Zero face energy → lpDb=null (not 0 dB).",
            ],
        }


class CsbinDecodeError(ValueError):
    """Surface .csbin present but not a valid RSBIN payload."""


def energy_sum_to_lp(energy: float) -> float | None:
    """Surface/coupe level as I-Simpa shows it (Recepteurs_surfacique.cpp).

    RSBIN cell values are intensity-like (cell energy / cell area), so the
    reference is 1e-12, not the punctual p0² = (20 µPa)².
    """
    if energy <= 0 or not math.isfinite(energy):
        return None
    return 10.0 * math.log10(energy / SURFACE_REF)


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
    truncated_ivec3: bool = False,
) -> None:
    """Write a minimal VERSION=3 RSBIN for unit tests (not from SPPS).

    Zero-energy faces get ``nbRecords=0`` like SPPS. ``truncated_ivec3``
    stores indices as Linux SPPS does: ``(a, 0, b)``.
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
            if truncated_ivec3:
                a, b, c = a, 0, b
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
            end = off + nb_rec * face_val_len
            if nb_rec < 0 or end > len(data):
                raise CsbinDecodeError("truncated faceValue")
            # timeStep uint16 at 0; energy float at end-4
            if face_val_len == _FACE_VALUE_SIZE:
                energy_sum = float(
                    sum(e for (e,) in struct.iter_unpack("<4xf", data[off:end]))
                )
            else:
                energy_sum = float(
                    sum(
                        struct.unpack_from("<f", data, p + face_val_len - 4)[0]
                        for p in range(off, end, face_val_len)
                    )
                )
            off = end
            faces_out.append(
                SurfaceFaceEnergy(
                    a=a,
                    b=b,
                    c=c,
                    energy_sum=energy_sum,
                    lp_db=energy_sum_to_lp(energy_sum),
                )
            )
        grid, layout = _decode_coupe_block(nodes, faces_out)
        blocks.append(
            SurfaceReceiverBlock(
                xml_index=int(xml_index),
                name=receiver_name or "surface",
                faces=faces_out,
                grid=grid,
                layout=layout,
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


def _coupe_write_order(
    faces: list[SurfaceFaceEnergy],
) -> tuple[int, int, int, str] | str:
    """(node base, nbRows, nbCols, indexLayout) of a SPPS coupe block, or a reason.

    SauveRecepteursSurfaciquesCoupe writes face ``2*(col + row*nbcols)`` as
    ``(base+col+1+row*nvc, base+col+row*nvc, base+col+(row+1)*nvc)``, nvc = nbcols+1.
    Linux SPPS memcpy's a ``long``-based ivec3 into three int32, so the file
    holds ``(a_lo, a_hi=0, b_lo)`` and vertex c is lost ("truncated_ivec3").
    Cells are therefore placed by write order, never by the stored c index.
    """
    if len(faces) < 2 or len(faces) % 2:
        return "face count is not two triangles per cell"
    f0, f1 = faces[0], faces[1]
    base = f0.a - 1
    if base < 0:
        return "first face vertex a < 1"
    if f0.c == base and f1.a == f0.a:
        layout = "truncated_ivec3"
        nvc = f1.c - base
    elif f0.b == base and f1.a == f0.a and f1.b == f0.c:
        layout = "exact"
        nvc = f0.c - base
    else:
        return "faces are not in SPPS coupe write order"
    nb_cols = nvc - 1
    cells = len(faces) // 2
    if nb_cols < 1 or cells % nb_cols:
        return f"cell count {cells} not divisible by nbCols {nb_cols}"
    return base, cells // nb_cols, nb_cols, layout


def _decode_coupe_block(
    nodes: list[tuple[float, float, float]],
    faces: list[SurfaceFaceEnergy],
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """Plan grid + layout diagnostics for one coupe receiver.

    Node ``base + col + row*nvc`` = B + row·stepU + col·stepV (BC = U, BA = V).
    The lattice is verified before use; a non-lattice block or a plane whose
    cells are not axis-aligned in XY yields no grid (map not published).
    Both triangles of a cell carry the same records (SPPS memcpy), so the
    cell value is taken once; it is cell energy / cell area as SPPS writes it.
    """
    order = _coupe_write_order(faces)
    if isinstance(order, str):
        return None, {"error": order}
    base, nb_rows, nb_cols, index_layout = order
    nvc = nb_cols + 1
    end = base + (nb_rows + 1) * nvc
    if end > len(nodes):
        return None, {"error": f"node block {base}..{end} exceeds {len(nodes)} nodes"}
    b = nodes[base]
    step_v = tuple(nodes[base + 1][k] - b[k] for k in range(3))
    step_u = tuple(nodes[base + nvc][k] - b[k] for k in range(3))
    tol = 1e-3 * max(math.hypot(*step_u), math.hypot(*step_v)) + 1e-4
    for row in range(nb_rows + 1):
        for col in range(nb_cols + 1):
            n = nodes[base + col + row * nvc]
            if any(
                abs(n[k] - (b[k] + row * step_u[k] + col * step_v[k])) > tol
                for k in range(3)
            ):
                return None, {"error": f"node ({row},{col}) off the coupe lattice"}

    layout: dict[str, Any] = {
        "nbRows": nb_rows,
        "nbCols": nb_cols,
        "indexLayout": index_layout,
    }
    energized = [
        (k // nb_cols, k % nb_cols)
        for k in range(nb_rows * nb_cols)
        if faces[2 * k].energy_sum > 0 and math.isfinite(faces[2 * k].energy_sum)
    ]
    layout["energizedCells"] = len(energized)
    if energized:
        layout.update(
            energizedRowMin=min(r for r, _ in energized),
            energizedRowMax=max(r for r, _ in energized),
            energizedColMin=min(c for _, c in energized),
            energizedColMax=max(c for _, c in energized),
        )

    def _axis(step: tuple[float, ...]) -> int | None:
        if abs(step[2]) > tol:
            return None
        if abs(step[1]) <= tol and abs(step[0]) > tol:
            return 0
        if abs(step[0]) <= tol and abs(step[1]) > tol:
            return 1
        return None

    u_axis, v_axis = _axis(step_u), _axis(step_v)
    if u_axis is None or v_axis is None or u_axis == v_axis:
        layout["error"] = "coupe cells are not axis-aligned in plan"
        return None, layout
    cell = {u_axis: abs(step_u[u_axis]), v_axis: abs(step_v[v_axis])}
    count = {u_axis: nb_rows, v_axis: nb_cols}
    block = nodes[base:end]
    min_x = min(n[0] for n in block)
    min_y = min(n[1] for n in block)
    nx, ny = count[0], count[1]
    lp_db: list[float | None] = [None] * (nx * ny)
    for k in range(nb_rows * nb_cols):
        row, col = divmod(k, nb_cols)
        cx = b[0] + (row + 0.5) * step_u[0] + (col + 0.5) * step_v[0]
        cy = b[1] + (row + 0.5) * step_u[1] + (col + 0.5) * step_v[1]
        i = min(nx - 1, max(0, int((cx - min_x) / cell[0])))
        j = min(ny - 1, max(0, int((cy - min_y) / cell[1])))
        lp_db[j * nx + i] = energy_sum_to_lp(faces[2 * k].energy_sum)
    if not any(v is not None for v in lp_db):
        return None, layout
    return {
        "originX": min_x,
        "originY": min_y,
        "cellSizeM": cell[0],
        "cellSizeYM": cell[1],
        "nx": nx,
        "ny": ny,
        "zM": sum(n[2] for n in block) / len(block),
        "lpDb": lp_db,
        "quantity": "Lp_dB",
        "unit": "dB",
        "source": "rsbin_coupe_write_order",
    }, layout


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

