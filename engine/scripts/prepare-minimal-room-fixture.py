#!/usr/bin/env python3
"""Prepare minimal_room inputs from pinned I-Simpa (no invented mesh).

Preferred on Linux CI with a local clone: prepare-minimal-room-fixture.sh.
This entrypoint also works on Windows by downloading the exact blobs from
raw.githubusercontent.com at the commit in engine/PINNED.json.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import urllib.request
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
ENGINE_DIR = SCRIPT_DIR.parent
PIN_FILE = ENGINE_DIR / "PINNED.json"
OUT_DIR = ENGINE_DIR / "fixtures" / "minimal_room" / "inputs"

UPSTREAM_FILES = {
    "mesh.cbin": "src/python_bindings/tests/mesh.cbin",
    "tetramesh.mbin": "src/python_bindings/tests/tetramesh.mbin",
    "speaker-test3.txt": "src/spps/tests/speaker-test3.txt",
}


def _download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "sonoplan-fixture"})
    with urllib.request.urlopen(req) as resp:
        data = resp.read()
    dest.write_bytes(data)


def main() -> int:
    pin = json.loads(PIN_FILE.read_text(encoding="utf-8"))
    commit = pin["isimpa"]["commit"]
    repo = pin["isimpa"]["repository"]
    slug = repo.rstrip("/").removesuffix(".git").split("github.com/")[-1]
    base = f"https://raw.githubusercontent.com/{slug}/{commit}"

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, rel in UPSTREAM_FILES.items():
        url = f"{base}/{rel}"
        dest = OUT_DIR / name
        print(f"download {url}")
        _download(url, dest)
        print(f"  -> {dest} ({dest.stat().st_size} bytes)")

    adapt = SCRIPT_DIR / "adapt-minimal-room-config.py"
    subprocess.check_call(
        [
            sys.executable,
            str(adapt),
            "--out",
            str(OUT_DIR / "config.xml"),
            "--nb-particles",
            "20000",
            "--seed",
            "1",
        ]
    )

    origin = f"""SonoPlan minimal_room SPPS inputs
=================================
I-Simpa repository: {repo}
Pinned commit: {commit}

Copied unchanged (official upstream test binaries / data):
  mesh.cbin          <- src/python_bindings/tests/mesh.cbin
  tetramesh.mbin     <- src/python_bindings/tests/tetramesh.mbin
  speaker-test3.txt  <- src/spps/tests/speaker-test3.txt

Generated (structure from src/spps/tests/config.xml, adapted for this mesh):
  config.xml
    - workingdirectory=./  (trailing slash required: SPPS concatenates workingDir+file)
    - modelName=mesh.cbin / tetrameshFileName=tetramesh.mbin
    - surface materials ids 100 and 101 (face idMat in mesh.cbin)
    - no surface receivers (mesh idRs=-1)
    - decimal separator: dot (ENG-007)
    - nbparticules=20000, random_seed=1 (seed!=0 required for SetRandSeed)
    - directivite=0 (omnidirectional; speaker-test3.txt kept for provenance)
    - rayon_recepteurp=2, duree_simulation=1, pasdetemps=5e-4
    - calc bands: 100 Hz and 1000 Hz only (CI smoke)

License: I-Simpa is GPLv3; redistributed test inputs retain upstream copyright.
See docs/engine-licenses.md.
"""
    (OUT_DIR / "ORIGIN.txt").write_text(origin, encoding="utf-8", newline="\n")

    lines: list[str] = []
    for name in (
        "config.xml",
        "mesh.cbin",
        "tetramesh.mbin",
        "speaker-test3.txt",
    ):
        digest = hashlib.sha256((OUT_DIR / name).read_bytes()).hexdigest()
        lines.append(f"{digest}  {name}")
    (OUT_DIR / "SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("FIXTURE_OK", OUT_DIR)
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
