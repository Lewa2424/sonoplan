#!/usr/bin/env python3
"""SonoPlan SPPS source patches — PAUSED (path A, 2026-10-16).

Experimental transforms (deposit-all receivers, link-all tetras, force cdt_vol,
binary patch marker) are **not** applied. They broke Build SPPS (marker
redefinition via documenting ``*.patch`` + string path) and did not prove
``energySumGlobal > 0`` on headless CI.

See ``docs/spps-energy-blocker.md``. Re-enable only in a dedicated energy stage
with a proven before/after on fixtures — do not invent dB.

This script only verifies the I-Simpa tree and that UTILISER stays defined
(the ``#ifndef UTILISER`` path does not compile against current core types).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ENGINE_DIR = Path(__file__).resolve().parent.parent
PATCH_DIR = ENGINE_DIR / "patches"


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if len(args) != 1:
        print(f"usage: {Path(__file__).name} <isimpa-src-dir>", file=sys.stderr)
        return 2
    src = Path(args[0]).resolve()
    core = src / "src" / "spps" / "CalculationCore.cpp"
    if not core.is_file():
        print(f"ERROR: not an I-Simpa tree: {src}", file=sys.stderr)
        return 1

    force = os.environ.get("SONOPLAN_APPLY_EXPERIMENTAL_SPPS_PATCHES", "").strip()
    if force in ("1", "true", "yes"):
        print(
            "ERROR: SONOPLAN_APPLY_EXPERIMENTAL_SPPS_PATCHES is set, but experimental "
            "apply code was removed for path A. Unset the env and use a dedicated "
            "energy-stage branch when ready. See docs/spps-energy-blocker.md.",
            file=sys.stderr,
        )
        return 1

    types = (src / "src" / "spps" / "sppsTypes.h").read_text(encoding="utf-8")
    if "#define UTILISER_MAILLAGE_OPTIMISATION" not in types:
        raise SystemExit(
            "ERROR: UTILISER must stay defined (ifndef path does not compile)"
        )

    paused = sorted(PATCH_DIR.glob("*.patch.paused"))
    documenting = sorted(PATCH_DIR.glob("*.patch"))
    print("SPPS patches PAUSED (path A) — no git apply, no string transforms")
    print(f"  tree: {src}")
    print(f"  documenting *.patch (ignored): {[p.name for p in documenting]}")
    print(f"  paused *.patch.paused: {[p.name for p in paused]}")
    print("  UTILISER kept; binary marker not required")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
