#!/usr/bin/env bash
# Run SPPS on a fixture workdir via Docker; then validate outputs with the adapter.
# Usage: ./run-spps-fixture.sh [fixture_workdir]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENGINE_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
PIN_FILE="${ENGINE_DIR}/PINNED.json"
COMMIT="$(python3 -c "import json; print(json.load(open('${PIN_FILE}'))['isimpa']['commit'])")"
IMAGE_TAG="sonoplan-spps:${COMMIT:0:12}"
WORK="${1:-${ENGINE_DIR}/fixtures/minimal_room/inputs}"

if ! command -v docker >/dev/null 2>&1; then
  echo "BLOCKER: docker not found — cannot run SPPS." >&2
  exit 2
fi

if [[ ! -f "${WORK}/config.xml" ]]; then
  echo "ERROR: ${WORK}/config.xml missing. Fixture binaries not yet produced (STG-01 incomplete)." >&2
  exit 3
fi

# ENG-004: pass config path as argv, no shell concatenation of user args.
docker run --rm -v "${WORK}:/work:rw" -w /work "${IMAGE_TAG}" /work/config.xml

python3 -m sonoplan_adapter.cli validate-outputs "${WORK}" \
  --manifest "${ENGINE_DIR}/fixtures/minimal_room/manifest.json"
