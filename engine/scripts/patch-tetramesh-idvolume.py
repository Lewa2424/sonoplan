#!/usr/bin/env python3
"""Force principal-volume idVolume=0 on a tetramesh.mbin.

Upstream ``lib_interface/tests/cube_mesh.mbin`` stores idVolume=1 on every
tetra. SPPS treats idVolume!=0 as an encombrement domain
(``InitEncombrementTetraLocalisation``). Official GUI scenes rematerialize
the principal volume as 0; the raw test binary does not.

This rewrite only changes the idVolume field (4 bytes × N tetras).
"""

from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path


def patch(path: Path, volume: int = 0) -> int:
    data = bytearray(path.read_bytes())
    n_t, n_n = struct.unpack_from("<II", data, 0)
    off = 8 + n_n * 12
    for _ in range(n_t):
        off += 16  # vertices
        struct.pack_into("<i", data, off, volume)
        off += 4
        off += 20 * 4  # 4 faces × 5 Intb
    path.write_bytes(data)
    return n_t


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("mbin", type=Path)
    p.add_argument("--volume", type=int, default=0)
    args = p.parse_args(argv)
    if not args.mbin.is_file():
        print(f"MISSING {args.mbin}", file=sys.stderr)
        return 1
    n = patch(args.mbin, args.volume)
    print(f"patched {n} tetras idVolume={args.volume} in {args.mbin}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
