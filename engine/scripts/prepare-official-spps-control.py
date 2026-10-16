#!/usr/bin/env python3
"""Prepare an unmodified-upstream SPPS control fixture for CI.

Copies I-Simpa ``src/spps/tests/config.xml`` + ``speaker-test3.txt`` and pairs
them with the official cube mesh (``lib_interface/tests/cube*.bin``).

Locale-only transforms (required for atof under LC_NUMERIC=C / ENG-007):
  - decimal commas → dots
  - workingdirectory → ``./``
  - random_seed forced to 1 (upstream 0 skips SetRandSeed / keeps multithread;
    not a physics change for energy>0 smoke)

No invented acoustic values. Does not rewrite materials, geometry, or Lw.
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path


def _locale_safe_config(text: str, *, seed: int) -> str:
    # Replace French decimal commas inside attribute values only.
    def repl_attr(m: re.Match[str]) -> str:
        return m.group(0).replace(",", ".")

    text = re.sub(r'="[^"]*"', repl_attr, text)
    text = re.sub(
        r'workingdirectory="[^"]*"',
        'workingdirectory="./"',
        text,
        count=1,
    )
    if seed == 0:
        raise ValueError("seed must be != 0 for CI single-thread smoke")
    text = re.sub(r'random_seed="[^"]*"', f'random_seed="{seed}"', text, count=1)
    # Ensure LF.
    return text.replace("\r\n", "\n")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--isimpa-root",
        type=Path,
        required=True,
        help="Checked-out I-Simpa tree at the pinned commit",
    )
    p.add_argument(
        "--out-dir",
        type=Path,
        required=True,
        help="Destination fixture inputs directory",
    )
    p.add_argument("--seed", type=int, default=1)
    args = p.parse_args(argv)

    root: Path = args.isimpa_root
    cfg_src = root / "src" / "spps" / "tests" / "config.xml"
    speaker = root / "src" / "spps" / "tests" / "speaker-test3.txt"
    mesh = root / "src" / "lib_interface" / "tests" / "cube.cbin"
    tetra = root / "src" / "lib_interface" / "tests" / "cube_mesh.mbin"
    for f in (cfg_src, speaker, mesh, tetra):
        if not f.is_file():
            print(f"MISSING {f}", file=sys.stderr)
            return 1

    out: Path = args.out_dir
    out.mkdir(parents=True, exist_ok=True)
    shutil.copy2(speaker, out / "speaker-test3.txt")
    shutil.copy2(mesh, out / "mesh.cbin")
    shutil.copy2(tetra, out / "tetramesh.mbin")

    raw = cfg_src.read_text(encoding="latin-1")
    safe = _locale_safe_config(raw, seed=args.seed)
    if re.search(r'="[^"]*,[^"]*"', safe):
        print("ERROR: comma decimal leaked after locale transform", file=sys.stderr)
        return 1
    (out / "config.xml").write_text(safe, encoding="utf-8")

    origin = (
        "SonoPlan official SPPS control fixture\n"
        f"I-Simpa root: {root}\n"
        "config.xml <- src/spps/tests/config.xml (commas→dots, workingdirectory=./, seed!=0)\n"
        "mesh.cbin / tetramesh.mbin <- src/lib_interface/tests/cube*.bin (unchanged bytes)\n"
        "speaker-test3.txt <- src/spps/tests/speaker-test3.txt (unchanged)\n"
    )
    (out / "ORIGIN.txt").write_text(origin, encoding="utf-8")
    print(f"wrote official control inputs under {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
