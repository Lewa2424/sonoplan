/**
 * Plausibility gate for an SPPS coupe grid before it is painted as a map.
 * Mirrors the adapter gate (job_run) so manifests stored before it still
 * cannot show a broken recording.
 */
import type { ResultManifestStub } from "../api/types";

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

/**
 * «notAWeighted» — задание до A-коррекции (только невзвешенный Lp);
 * «noFrame» — неизвестна привязка сетки к координатам проекта.
 */
export type SurfaceMapRejectReason =
  | SurfaceGridRejectReason
  | "notAWeighted"
  | "noFrame";

/** Сетка карты в координатах проекта, уровни в дБА. */
export interface PlanSurfaceGrid {
  readonly originX: number;
  readonly originY: number;
  readonly cellSizeM: number;
  readonly cellSizeYM: number;
  readonly nx: number;
  readonly ny: number;
  readonly zM: number | null;
  readonly laDb: readonly (number | null)[];
}

export type SurfaceMapResult =
  | { readonly ok: true; readonly grid: PlanSurfaceGrid }
  | { readonly ok: false; readonly reason: SurfaceMapRejectReason };

/** null — карты в манифесте нет (не опубликована адаптером). */
export function surfaceMapFromManifest(
  manifest: ResultManifestStub | null | undefined,
): SurfaceMapResult | null {
  if (manifest?.mapAvailable !== true) return null;
  const g = manifest.grid;
  if (
    !g ||
    typeof g.originX !== "number" ||
    typeof g.originY !== "number" ||
    typeof g.cellSizeM !== "number" ||
    typeof g.nx !== "number" ||
    typeof g.ny !== "number" ||
    !Array.isArray(g.lpDb)
  ) {
    return { ok: false, reason: "dimensions" };
  }
  const gate = surfaceGridRejectReason({ nx: g.nx, ny: g.ny, lpDb: g.lpDb });
  if (gate !== null) return { ok: false, reason: gate };
  if (!Array.isArray(g.laDb) || g.laDb.length < g.nx * g.ny) {
    return { ok: false, reason: "notAWeighted" };
  }
  const meta = manifest.exportMeta;
  if (
    meta?.mode !== "export_box" ||
    typeof meta.originX !== "number" ||
    typeof meta.originY !== "number"
  ) {
    return { ok: false, reason: "noFrame" };
  }
  const cellY =
    typeof g.cellSizeYM === "number" && g.cellSizeYM > 0 ? g.cellSizeYM : g.cellSizeM;
  return {
    ok: true,
    grid: {
      originX: meta.originX + g.originX,
      originY: meta.originY + g.originY,
      cellSizeM: g.cellSizeM,
      cellSizeYM: cellY,
      nx: g.nx,
      ny: g.ny,
      zM: typeof g.zM === "number" ? g.zM : null,
      laDb: g.laDb,
    },
  };
}
