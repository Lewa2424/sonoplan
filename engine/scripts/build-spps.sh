#!/usr/bin/env bash
# Optional SPPS build via Docker Engine on Linux (VPS/CI with docker).
# Primary path without Docker Desktop: build-spps-native.sh or GitHub Actions.
# See docs/engine-build-without-docker.md
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENGINE_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
PIN_FILE="${ENGINE_DIR}/PINNED.json"
COMMIT="$(python3 -c "import json; print(json.load(open('${PIN_FILE}'))['isimpa']['commit'])")"
IMAGE_TAG="sonoplan-spps:${COMMIT:0:12}"

cd "${ENGINE_DIR}"

if ! command -v docker >/dev/null 2>&1; then
  echo "BLOCKER: docker not found." >&2
  echo "Primary path (no Docker Desktop): native Linux / GitHub Actions:" >&2
  echo "  ./scripts/build-spps-native.sh" >&2
  echo "  or: Actions → Build SPPS (workflow_dispatch)" >&2
  echo "See: docs/engine-build-without-docker.md" >&2
  echo "Optional Docker-on-Linux command:" >&2
  echo "  docker build --build-arg ISIMPA_COMMIT=${COMMIT} -t ${IMAGE_TAG} -f Dockerfile ." >&2
  exit 2
fi

echo "Building ${IMAGE_TAG} (ISIMPA_COMMIT=${COMMIT}) ..."
docker build \
  --build-arg "ISIMPA_COMMIT=${COMMIT}" \
  -t "${IMAGE_TAG}" \
  -f Dockerfile \
  .

DIGEST="$(docker image inspect "${IMAGE_TAG}" --format '{{index .RepoDigests 0}}' 2>/dev/null || true)"
ID="$(docker image inspect "${IMAGE_TAG}" --format '{{.Id}}')"
echo "BUILD_OK image=${IMAGE_TAG}"
echo "IMAGE_ID=${ID}"
echo "REPO_DIGEST=${DIGEST:-"(local only — push/registry digest not set)"}"
echo "Next: record image Id/digest into PINNED.json image_checksum after verification."
echo "Smoke: docker run --rm ${IMAGE_TAG}  (expect usage / non-silent failure without config)"
