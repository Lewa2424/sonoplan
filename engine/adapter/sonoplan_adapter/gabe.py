"""GABE (Generic Array Binary Exchange) reader — matches libsimpa formatGABE::GABE::Load.

Upstream: I-Simpa `src/lib_interface/input_output/gabe/gabe.cpp` @ pinned commit.
`.recp` / `.gabe` / `.recps` share this binary container; extension alone is not CSV.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path
from typing import Any


class GabeObjectType(IntEnum):
    """formatGABE::GABE_OBJECTTYPE (gabe.h)."""

    USER_DEFINED = 49
    FLOAT = 50
    INT = 51
    SHORTSTRING = 52


STRING_LABEL_LENGTH = 255
SHORT_STRING_CELL = 50
GABE_VERSION = 2


@dataclass(frozen=True)
class GabeColumn:
    col_type: GabeObjectType
    label: str
    rows: int
    # Exactly one of strings / floats / ints is populated for known types.
    strings: tuple[str, ...] | None = None
    floats: tuple[float, ...] | None = None
    ints: tuple[int, ...] | None = None
    float_digits: int | None = None

    def as_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "colType": int(self.col_type),
            "colTypeName": self.col_type.name,
            "label": self.label,
            "rows": self.rows,
        }
        if self.strings is not None:
            out["strings"] = list(self.strings)
        if self.floats is not None:
            out["floats"] = list(self.floats)
            out["floatDigits"] = self.float_digits
        if self.ints is not None:
            out["ints"] = list(self.ints)
        return out


@dataclass(frozen=True)
class GabeTable:
    format_version: int
    read_only: bool
    columns: tuple[GabeColumn, ...]
    source_path: str

    @property
    def ncols(self) -> int:
        return len(self.columns)


class GabeFormatError(ValueError):
    """File is not a readable GABE table (truncated, unknown version, bad layout)."""


def load_gabe(path: Path | str) -> GabeTable:
    """Load a GABE binary file using the same field order/padding as libsimpa Load()."""
    p = Path(path)
    data = p.read_bytes()
    off = 0

    if len(data) < 20:
        raise GabeFormatError(f"file too short for GABE header: {p}")

    format_version, _hlen, _chlen, cols = struct.unpack_from("<iiii", data, off)
    off += 16
    if format_version > GABE_VERSION:
        raise GabeFormatError(
            f"unsupported GABE formatVersion={format_version} (max {GABE_VERSION})"
        )
    if cols < 0:
        raise GabeFormatError(f"invalid cols={cols}")

    read_only = bool(data[off])
    off += 1
    off += 3  # libsimpa: seekg(3) after bool

    columns: list[GabeColumn] = []
    for _ in range(cols):
        if off + 2 + 2 + 4 + 8 + 8 + STRING_LABEL_LENGTH + 1 > len(data):
            raise GabeFormatError(f"truncated column header at offset {off}")

        (col_type_raw,) = struct.unpack_from("<H", data, off)
        off += 2
        off += 2  # seekg(2)
        (rows,) = struct.unpack_from("<i", data, off)
        off += 4
        (sizeof_col,) = struct.unpack_from("<q", data, off)
        off += 8
        (_sizeof_header,) = struct.unpack_from("<q", data, off)
        off += 8
        label_raw = data[off : off + STRING_LABEL_LENGTH]
        off += STRING_LABEL_LENGTH
        off += 1  # seekg(1)
        label = label_raw.split(b"\x00", 1)[0].decode("latin-1", errors="replace")

        try:
            col_type = GabeObjectType(col_type_raw)
        except ValueError:
            # Unknown column: skip payload using sizeofCol (libsimpa behaviour).
            if sizeof_col < 0 or off + sizeof_col > len(data):
                raise GabeFormatError(
                    f"unknown colType={col_type_raw} with bad sizeofCol={sizeof_col}"
                ) from None
            off += int(sizeof_col)
            continue

        if rows < 0:
            raise GabeFormatError(f"invalid rows={rows} for column {label!r}")

        if col_type is GabeObjectType.SHORTSTRING:
            off += 1  # ReadFile seekg(1)
            need = SHORT_STRING_CELL * rows
            if off + need > len(data):
                raise GabeFormatError(f"truncated SHORTSTRING column {label!r}")
            cells: list[str] = []
            for i in range(rows):
                cell = data[off + i * SHORT_STRING_CELL : off + (i + 1) * SHORT_STRING_CELL]
                cells.append(cell.split(b"\x00", 1)[0].decode("latin-1", errors="replace"))
            off += need
            columns.append(
                GabeColumn(
                    col_type=col_type,
                    label=label,
                    rows=rows,
                    strings=tuple(cells),
                )
            )
        elif col_type is GabeObjectType.FLOAT:
            if off + 4 + 4 * rows > len(data):
                raise GabeFormatError(f"truncated FLOAT column {label!r}")
            (digits,) = struct.unpack_from("<i", data, off)
            off += 4
            floats = struct.unpack_from("<" + ("f" * rows), data, off)
            off += 4 * rows
            columns.append(
                GabeColumn(
                    col_type=col_type,
                    label=label,
                    rows=rows,
                    floats=tuple(floats),
                    float_digits=digits,
                )
            )
        elif col_type is GabeObjectType.INT:
            off += 1  # ReadFile seekg(1)
            if off + 4 * rows > len(data):
                raise GabeFormatError(f"truncated INT column {label!r}")
            ints = struct.unpack_from("<" + ("i" * rows), data, off)
            off += 4 * rows
            columns.append(
                GabeColumn(
                    col_type=col_type,
                    label=label,
                    rows=rows,
                    ints=tuple(ints),
                )
            )
        else:
            if sizeof_col < 0 or off + sizeof_col > len(data):
                raise GabeFormatError(f"USER_DEFINED bad sizeofCol for {label!r}")
            off += int(sizeof_col)

    if off != len(data):
        raise GabeFormatError(
            f"trailing bytes after GABE parse: offset={off} size={len(data)} path={p}"
        )

    return GabeTable(
        format_version=format_version,
        read_only=read_only,
        columns=tuple(columns),
        source_path=str(p),
    )
