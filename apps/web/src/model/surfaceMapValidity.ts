/**
 * Plausibility gate for an SPPS coupe grid before it is painted as a map.
 * Mirrors the adapter gate (job_run) so manifests stored before it still
 * cannot show a broken recording.
 */

export const MIN_SURFACE_FILL = 0.45;
/** Coupe overhangs all walls of a closed room — energy must reach its far edges. */
export const MIN_SURFACE_SPAN = 0.9;

export type SurfaceGridRejectReason = "dimensions" | "sparse" | "partialCoverage";

export function surfaceGridRejectReason(grid: {
  readonly nx: number;
  readonly ny: number;
  readonly lpDb: readonly (number | null | undefined)[];
}): SurfaceGridRejectReason | null {
  const { nx, ny, lpDb } = grid;
  if (!Number.isInteger(nx) || !Number.isInteger(ny) || nx < 1 || ny < 1) {
    return "dimensions";
  }
  if (lpDb.length < nx * ny) return "dimensions";

  let filled = 0;
  let minI = nx;
  let maxI = -1;
  let minJ = ny;
  let maxJ = -1;
  for (let k = 0; k < nx * ny; k += 1) {
    const v = lpDb[k];
    if (v === null || v === undefined) continue;
    filled += 1;
    const i = k % nx;
    const j = Math.floor(k / nx);
    if (i < minI) minI = i;
    if (i > maxI) maxI = i;
    if (j < minJ) minJ = j;
    if (j > maxJ) maxJ = j;
  }
  if (filled / (nx * ny) < MIN_SURFACE_FILL) return "sparse";
  const spanX = (maxI - minI + 1) / nx;
  const spanY = (maxJ - minJ + 1) / ny;
  if (spanX < MIN_SURFACE_SPAN || spanY < MIN_SURFACE_SPAN) {
    return "partialCoverage";
  }
  return null;
}
