#!/usr/bin/env bash
# Prepare engine/fixtures/minimal_room/inputs from pinned I-Simpa test data.
#
# Copies official binaries (does NOT invent mesh):
#   src/lib_interface/tests/cube.cbin       → mesh.cbin (5×5×5 m)
#   src/lib_interface/tests/cube_mesh.mbin  → tetramesh.mbin
#   src/spps/tests/speaker-test3.txt
# Generates config.xml via adapt-minimal-room-config.py (material id 0,
# workingdirectory=., dots locale, CI smoke particle count).
#
# Usage (from repo root):
#   ./engine/scripts/prepare-minimal-room-fixture.sh
#   ISIMPA_SRC=/path/to/isimpa ./engine/scripts/prepare-minimal-room-fixture.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENGINE_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_ROOT="$(cd "${ENGINE_DIR}/.." && pwd)"
PIN_FILE="${ENGINE_DIR}/PINNED.json"
OUT_DIR="${ENGINE_DIR}/fixtures/minimal_room/inputs"
NB_PARTICLES="${NB_PARTICLES:-20000}"
# SPPS SetRandSeed only when seed!=0; also forces single-thread.
SEED="${SEED:-1}"

COMMIT="$(python3 -c "import json; print(json.load(open('${PIN_FILE}'))['isimpa']['commit'])")"
REPO="$(python3 -c "import json; print(json.load(open('${PIN_FILE}'))['isimpa']['repository'])")"

if [[ -n "${ISIMPA_SRC:-}" ]]; then
  SRC="$(cd "${ISIMPA_SRC}" && pwd)"
else
  "${SCRIPT_DIR}/fetch-isimpa.sh"
  SRC="${ENGINE_DIR}/.cache/isimpa"
fi

ACTUAL="$(git -C "${SRC}" rev-parse HEAD)"
if [[ "${ACTUAL}" != "${COMMIT}" ]]; then
  echo "ERROR: expected I-Simpa ${COMMIT}, got ${ACTUAL} in ${SRC}" >&2
  exit 1
fi

MESH_SRC="${SRC}/src/lib_interface/tests/cube.cbin"
TETRA_SRC="${SRC}/src/lib_interface/tests/cube_mesh.mbin"
SPEAKER_SRC="${SRC}/src/spps/tests/speaker-test3.txt"

for f in "${MESH_SRC}" "${TETRA_SRC}" "${SPEAKER_SRC}"; do
  if [[ ! -f "${f}" ]]; then
    echo "ERROR: missing upstream file: ${f}" >&2
    exit 1
  fi
done

mkdir -p "${OUT_DIR}"
cp -a "${MESH_SRC}" "${OUT_DIR}/mesh.cbin"
cp -a "${TETRA_SRC}" "${OUT_DIR}/tetramesh.mbin"
cp -a "${SPEAKER_SRC}" "${OUT_DIR}/speaker-test3.txt"

python3 "${SCRIPT_DIR}/adapt-minimal-room-config.py" \
  --out "${OUT_DIR}/config.xml" \
  --nb-particles "${NB_PARTICLES}" \
  --seed "${SEED}"

# Provenance / license notice (GPLv3 I-Simpa test data).
cat > "${OUT_DIR}/ORIGIN.txt" <<EOF
SonoPlan minimal_room SPPS inputs
=================================
I-Simpa repository: ${REPO}
Pinned commit: ${COMMIT}

Copied unchanged (official upstream test binaries / data):
  mesh.cbin          <- src/lib_interface/tests/cube.cbin (5x5x5 m, idMat=0)
  tetramesh.mbin     <- src/lib_interface/tests/cube_mesh.mbin
  speaker-test3.txt  <- src/spps/tests/speaker-test3.txt

Generated (structure from src/spps/tests/config.xml, adapted for this mesh):
  config.xml
    - workingdirectory=./  (trailing slash required: SPPS concatenates workingDir+file)
    - modelName=mesh.cbin / tetrameshFileName=tetramesh.mbin
    - surface material id 0 (face idMat in cube.cbin)
    - no surface receivers (mesh idRs=-1)
    - decimal separator: dot (ENG-007); runner forces LC_NUMERIC=C
    - nbparticules=${NB_PARTICLES}, random_seed=${SEED}
    - directivite=0, rayon_recepteurp=1, duree_simulation=1, pasdetemps=5e-4
    - calc bands: 100 Hz and 1000 Hz only (CI smoke)

License: I-Simpa is GPLv3; redistributed test inputs retain upstream copyright.
See docs/engine-licenses.md.
EOF

# Checksums for reproducibility
(
  cd "${OUT_DIR}"
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum config.xml mesh.cbin tetramesh.mbin speaker-test3.txt > SHA256SUMS
  else
    shasum -a 256 config.xml mesh.cbin tetramesh.mbin speaker-test3.txt > SHA256SUMS
  fi
)

echo "FIXTURE_OK out=${OUT_DIR}"
ls -la "${OUT_DIR}"
cat "${OUT_DIR}/SHA256SUMS"
