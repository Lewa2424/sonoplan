/**
 * Предварительная оценка Lp по формуле помещения (прямое + диффузное поле):
 *   Lp,band = Lw,band + 10·lg(Q / (4π r²) + 4 / R),  R = S·ᾱ / (1 − ᾱ).
 *
 * Это не SPPS и не замена проверенного расчёта (ТЗ OPT-010): не учитывает
 * экраны/препятствия, неравномерность поглощения, форму помещения, воздух.
 * Источники и полосы складываются по энергии; при weighting «A» коррекция
 * применяется один раз к каждой невзвешенной полосе до суммирования.
 */
import { aWeightingDb, type LevelWeighting } from "./aWeighting.js";
import { pointInPolygon, stripClosingDuplicate } from "./geometry.js";
import type { FloorVertex, ModelSnapshot } from "./types.js";

/** Всенаправленный источник в свободном поле (как directivite=0 в SPPS). */
const DIRECTIVITY_Q = 1;
/**
 * Нижний предел расстояния источник–приёмник: формула точечного источника
 * расходится при r → 0, а реальный агрегат имеет габариты порядка метра.
 */
export const DIFFUSE_MIN_DISTANCE_M = 0.5;

export type DiffuseEstimateUnavailableReason =
  | "no_room"
  | "room_height_unknown"
  | "room_contour_degenerate"
  | "no_material"
  | "no_sources"
  | "no_common_bands";

export interface DiffuseFieldSource {
  readonly x: number;
  readonly y: number;
  readonly z: number;
  /** Lw по полосам, дБ re 1 пВт (только известные значения). */
  readonly lwByBandHz: ReadonlyMap<number, number>;
}

export interface DiffuseFieldInput {
  readonly contour: readonly FloorVertex[];
  readonly floorAreaM2: number;
  readonly totalSurfaceM2: number;
  readonly volumeM3: number;
  /** Полосы, где известны и α, и Lw хотя бы одного источника. */
  readonly bandsHz: readonly number[];
  /** Постоянная помещения R по полосе, м²; Infinity при ᾱ ≥ 1. */
  readonly roomConstantByBandHz: ReadonlyMap<number, number>;
  readonly sources: readonly DiffuseFieldSource[];
}

export type DiffuseFieldInputResult =
  | { readonly ok: true; readonly input: DiffuseFieldInput }
  | { readonly ok: false; readonly reason: DiffuseEstimateUnavailableReason };

function polygonAreaAndPerimeter(ring: readonly FloorVertex[]): {
  area: number;
  perimeter: number;
} {
  let twiceArea = 0;
  let perimeter = 0;
  for (let i = 0; i < ring.length; i++) {
    const a = ring[i]!;
    const b = ring[(i + 1) % ring.length]!;
    twiceArea += a.x * b.y - b.x * a.y;
    perimeter += Math.hypot(b.x - a.x, b.y - a.y);
  }
  return { area: Math.abs(twiceArea) / 2, perimeter };
}

/** Собрать вход оценки из черновика; неизвестное → причина, а не 0. */
export function buildDiffuseFieldInput(
  model: ModelSnapshot,
): DiffuseFieldInputResult {
  const room = model.rooms[0];
  if (!room) return { ok: false, reason: "no_room" };
  const height = room.heightM.value;
  if (height === null || !Number.isFinite(height) || height <= 0) {
    return { ok: false, reason: "room_height_unknown" };
  }
  const ring = stripClosingDuplicate(room.floorContour);
  if (ring.length < 3) return { ok: false, reason: "room_contour_degenerate" };
  const { area, perimeter } = polygonAreaAndPerimeter(ring);
  if (!(area > 0)) return { ok: false, reason: "room_contour_degenerate" };

  // Same pick as the SPPS export: room material, else first material.
  const material =
    model.materials.find((m) => m.id === room.materialVersionId) ??
    model.materials[0] ??
    null;
  if (!material) return { ok: false, reason: "no_material" };

  const sources: DiffuseFieldSource[] = [];
  for (const s of model.sources) {
    const lw = new Map<number, number>();
    for (const band of s.powerSpectrumLw) {
      const v = band.level.value;
      if (v !== null && Number.isFinite(v)) lw.set(band.bandHz, v);
    }
    if (lw.size > 0) {
      sources.push({ x: s.position.x, y: s.position.y, z: s.position.z, lwByBandHz: lw });
    }
  }
  if (sources.length === 0) return { ok: false, reason: "no_sources" };

  const totalSurface = 2 * area + perimeter * height;
  const roomConstant = new Map<number, number>();
  const bands: number[] = [];
  for (const band of material.absorptionByBand) {
    const alpha = band.alpha;
    if (alpha === null || !Number.isFinite(alpha) || alpha <= 0) continue;
    if (!sources.some((s) => s.lwByBandHz.has(band.bandHz))) continue;
    roomConstant.set(
      band.bandHz,
      alpha >= 1 ? Infinity : (totalSurface * alpha) / (1 - alpha),
    );
    bands.push(band.bandHz);
  }
  if (bands.length === 0) return { ok: false, reason: "no_common_bands" };
  bands.sort((a, b) => a - b);

  return {
    ok: true,
    input: {
      contour: ring,
      floorAreaM2: area,
      totalSurfaceM2: totalSurface,
      volumeM3: area * height,
      bandsHz: bands,
      roomConstantByBandHz: roomConstant,
      sources,
    },
  };
}

function bandWeightDb(bandHz: number, weighting: LevelWeighting): number {
  if (weighting === "Z") return 0;
  const a = aWeightingDb(bandHz);
  if (a === null) {
    throw new RangeError(`A-weighting unknown for ${bandHz} Hz (not a nominal band)`);
  }
  return a;
}

/** Суммарный Lp в точке (дБА при «A», дБ при «Z»); null, если энергии нет. */
export function estimateLpAt(
  input: DiffuseFieldInput,
  x: number,
  y: number,
  z: number,
  weighting: LevelWeighting,
): number | null {
  let total = 0;
  for (const hz of input.bandsHz) {
    const r = input.roomConstantByBandHz.get(hz)!;
    const reverberant = Number.isFinite(r) ? 4 / r : 0;
    const weight = bandWeightDb(hz, weighting);
    for (const s of input.sources) {
      const lw = s.lwByBandHz.get(hz);
      if (lw === undefined) continue;
      const dist = Math.max(
        Math.hypot(x - s.x, y - s.y, z - s.z),
        DIFFUSE_MIN_DISTANCE_M,
      );
      const direct = DIRECTIVITY_Q / (4 * Math.PI * dist * dist);
      total += 10 ** ((lw + weight) / 10) * (direct + reverberant);
    }
  }
  return total > 0 ? 10 * Math.log10(total) : null;
}

export interface DiffuseFieldGrid {
  readonly originX: number;
  readonly originY: number;
  readonly cellSizeM: number;
  readonly nx: number;
  readonly ny: number;
  readonly zM: number;
  readonly weighting: LevelWeighting;
  /** Row-major, строка 0 = min Y; вне контура → null. */
  readonly lpDb: readonly (number | null)[];
}

/** Горизонтальная сетка оценки по габариту контура; шаг по умолчанию ~1/80 меньшей стороны. */
export function estimateLpGrid(
  input: DiffuseFieldInput,
  zM: number,
  weighting: LevelWeighting,
  cellSizeM?: number,
): DiffuseFieldGrid {
  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;
  for (const v of input.contour) {
    minX = Math.min(minX, v.x);
    minY = Math.min(minY, v.y);
    maxX = Math.max(maxX, v.x);
    maxY = Math.max(maxY, v.y);
  }
  const w = maxX - minX;
  const d = maxY - minY;
  const cell =
    cellSizeM ?? Math.min(0.5, Math.max(0.1, Math.min(w, d) / 80));
  const nx = Math.max(1, Math.ceil(w / cell));
  const ny = Math.max(1, Math.ceil(d / cell));
  const lpDb: (number | null)[] = new Array(nx * ny);
  for (let j = 0; j < ny; j++) {
    const cy = minY + (j + 0.5) * cell;
    for (let i = 0; i < nx; i++) {
      const cx = minX + (i + 0.5) * cell;
      lpDb[j * nx + i] = pointInPolygon({ x: cx, y: cy }, input.contour)
        ? estimateLpAt(input, cx, cy, zM, weighting)
        : null;
    }
  }
  return { originX: minX, originY: minY, cellSizeM: cell, nx, ny, zM, weighting, lpDb };
}
