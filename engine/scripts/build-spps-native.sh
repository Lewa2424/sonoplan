#!/usr/bin/env bash
# Native Linux SPPS build (GitHub Actions / remote VPS/VM).
# No Docker Desktop required. Docker-on-Linux remains optional via build-spps.sh.
#
# Usage (from repo root or engine/):
#   ./engine/scripts/build-spps-native.sh
#   ISIMPA_SRC=/path/to/isimpa ./engine/scripts/build-spps-native.sh
#
# Outputs under engine/dist/:
#   spps                     — binary
#   ORIGIN.txt               — source path of the binary inside the build tree
#   SHA256SUMS               — checksum of spps
#   spps-linux-*.tar.gz      — archive for CI artifact upload
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENGINE_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
PIN_FILE="${ENGINE_DIR}/PINNED.json"
PATCH_DIR="${ENGINE_DIR}/patches"
DIST_DIR="${ENGINE_DIR}/dist"
CPM_SOURCE_CACHE="${CPM_SOURCE_CACHE:-${HOME}/.cache/CPM}"
BUILD_TYPE="${BUILD_TYPE:-Release}"
JOBS="${JOBS:-$(nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 2)}"

if ! command -v python3 >/dev/null 2>&1; then
  echo "BLOCKER: python3 required to read PINNED.json" >&2
  exit 2
fi
if ! command -v cmake >/dev/null 2>&1; then
  echo "BLOCKER: cmake not found. Install build deps (see docs/engine-build-without-docker.md)." >&2
  exit 2
fi
if ! command -v git >/dev/null 2>&1; then
  echo "BLOCKER: git not found." >&2
  exit 2
fi

COMMIT="$(python3 -c "import json; print(json.load(open('${PIN_FILE}'))['isimpa']['commit'])")"
REPO="$(python3 -c "import json; print(json.load(open('${PIN_FILE}'))['isimpa']['repository'])")"
SHORT="${COMMIT:0:12}"

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

# SonoPlan patches (deposit-on-start-tetra + link-all-tetras-within-rayon)
echo "Applying SPPS patches via apply-spps-patches.py ..."
python3 "${ENGINE_DIR}/scripts/apply-spps-patches.py" "${SRC}"
# Fail fast if the UTILISER-path smoke fix is missing (string fallback must land).
if ! grep -q "SonoPlan: ensure every tetra that can intersect" \
    "${SRC}/src/spps/sppsInitialisation.cpp"; then
  echo "ERROR: patch 0002 (link-all-tetras) not present after apply" >&2
  exit 1
fi

mkdir -p "${SRC}/build" "${DIST_DIR}" "${CPM_SOURCE_CACHE}"
cd "${SRC}/build"

cmake .. \
  -DCPM_SOURCE_CACHE="${CPM_SOURCE_CACHE}" \
  -DCMAKE_BUILD_TYPE="${BUILD_TYPE}" \
  -DSKIPISIMPA=ON

cmake --build . --parallel "${JOBS}"
cmake --install .

SPPS_BIN="$(find "${SRC}" -type f -name spps -perm -111 | head -n 1)"
if [[ -z "${SPPS_BIN}" ]]; then
  echo "ERROR: spps binary not found after install under ${SRC}" >&2
  exit 1
fi

cp -a "${SPPS_BIN}" "${DIST_DIR}/spps"
# Fail the job if the patched marker never made it into the linked binary.
if ! grep -a -q "sonoplan-deposit-start-tetra-v2" "${DIST_DIR}/spps"; then
  echo "ERROR: patched marker not found inside spps binary (stale/unpatched build)" >&2
  exit 1
fi
printf 'SPPS_BIN=%s\nISIMPA_COMMIT=%s\nBUILD_TYPE=%s\nSONOPLAN_PATCH=%s\n' \
  "${SPPS_BIN}" "${COMMIT}" "${BUILD_TYPE}" "deposit-start-tetra-v2" \
  > "${DIST_DIR}/ORIGIN.txt"

(
  cd "${DIST_DIR}"
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum spps > SHA256SUMS
  else
    shasum -a 256 spps > SHA256SUMS
  fi
)

ARCHIVE_NAME="spps-linux-x86_64-${SHORT}.tar.gz"
tar -C "${DIST_DIR}" -czf "${DIST_DIR}/${ARCHIVE_NAME}" spps ORIGIN.txt SHA256SUMS

echo "BUILD_OK commit=${COMMIT}"
echo "SPPS_BIN=${DIST_DIR}/spps"
echo "ARCHIVE=${DIST_DIR}/${ARCHIVE_NAME}"
echo "SHA256SUMS:"
cat "${DIST_DIR}/SHA256SUMS"
echo "Next: record binary sha256 into PINNED.json → binary_checksum after verification."
# Smoke: binary should print usage / fail without config (non-silent)
"${DIST_DIR}/spps" 2>&1 | head -n 5 || true
