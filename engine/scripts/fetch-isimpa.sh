#!/usr/bin/env bash
# Clone I-Simpa at the pinned commit into engine/.cache (gitignored).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENGINE_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
PIN_FILE="${ENGINE_DIR}/PINNED.json"

COMMIT="$(python3 -c "import json; print(json.load(open('${PIN_FILE}'))['isimpa']['commit'])")"
REPO="$(python3 -c "import json; print(json.load(open('${PIN_FILE}'))['isimpa']['repository'])")"
DEST="${ENGINE_DIR}/.cache/isimpa"

mkdir -p "$(dirname "${DEST}")"
if [[ -d "${DEST}/.git" ]]; then
  # reset --hard: checkout --force is a no-op when HEAD is already COMMIT,
  # leaving prior SonoPlan patch edits in the working tree (CI cache reuse).
  git -C "${DEST}" fetch --depth=1 origin "${COMMIT}"
  git -C "${DEST}" reset --hard "${COMMIT}"
else
  git clone --filter=blob:none "${REPO}" "${DEST}"
  git -C "${DEST}" checkout "${COMMIT}"
fi

ACTUAL="$(git -C "${DEST}" rev-parse HEAD)"
if [[ "${ACTUAL}" != "${COMMIT}" ]]; then
  echo "ERROR: expected ${COMMIT}, got ${ACTUAL}" >&2
  exit 1
fi
echo "OK: I-Simpa at ${ACTUAL} -> ${DEST}"
