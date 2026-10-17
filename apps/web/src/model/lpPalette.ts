/**
 * Фиксированная шкала карты уровня, дБА: классы по 5 дБ, ≤60 … >105.
 * Цвета — абсолютная шкала DIN 45682:2020 (схема vs5.b, coloringnoise.com),
 * сдвинутая на +30 дБ под производственное помещение: граница
 * «сине-зелёный → оранжевый» приходится на 80 дБА (норма на рабочем месте).
 * Внутри шкалы цвет плавно интерполируется между центрами классов.
 */

export interface NoiseClass {
  /** Нижняя граница, дБА; null — открытый класс «≤ upper». */
  readonly lowerDb: number | null;
  /** Верхняя граница, дБА; null — открытый класс «> lower». */
  readonly upperDb: number | null;
  readonly rgb: readonly [number, number, number];
}

export const NOISE_SCALE_UNIT = "дБА";
const FIRST_UPPER_DB = 60;
const STEP_DB = 5;

const DIN_45682_RGB: readonly (readonly [number, number, number])[] = [
  [130, 166, 173],
  [160, 186, 191],
  [184, 214, 209],
  [206, 228, 204],
  [226, 242, 191],
  [243, 198, 131],
  [232, 126, 77],
  [205, 70, 62],
  [161, 26, 77],
  [117, 8, 92],
  [67, 10, 74],
];

export const NOISE_CLASSES: readonly NoiseClass[] = DIN_45682_RGB.map((rgb, i) => ({
  lowerDb: i === 0 ? null : FIRST_UPPER_DB + (i - 1) * STEP_DB,
  upperDb: i === DIN_45682_RGB.length - 1 ? null : FIRST_UPPER_DB + i * STEP_DB,
  rgb,
}));

/** Центры классов: открытые крайние классы — на полшага за границей. */
const ANCHORS_DB = NOISE_CLASSES.map(
  (_, i) => FIRST_UPPER_DB - STEP_DB / 2 + i * STEP_DB,
);

/** Прозрачность ячейки карты: план под ней остаётся читаемым. */
const CELL_ALPHA = 215;

export function noiseRgb(levelDb: number): [number, number, number] {
  const first = ANCHORS_DB[0]!;
  const last = ANCHORS_DB[ANCHORS_DB.length - 1]!;
  if (levelDb <= first) return [...DIN_45682_RGB[0]!];
  if (levelDb >= last) return [...DIN_45682_RGB[DIN_45682_RGB.length - 1]!];
  const pos = (levelDb - first) / STEP_DB;
  const i = Math.floor(pos);
  const u = pos - i;
  const a = DIN_45682_RGB[i]!;
  const b = DIN_45682_RGB[i + 1]!;
  return [
    Math.round(a[0] + (b[0] - a[0]) * u),
    Math.round(a[1] + (b[1] - a[1]) * u),
    Math.round(a[2] + (b[2] - a[2]) * u),
  ];
}

/** null / нет энергии → прозрачно (не «тишина»). */
export function lpToRgba(
  lpDb: number | null | undefined,
): [number, number, number, number] {
  if (lpDb === null || lpDb === undefined || !Number.isFinite(lpDb)) {
    return [0, 0, 0, 0];
  }
  const [r, g, b] = noiseRgb(lpDb);
  return [r, g, b, CELL_ALPHA];
}

/** CSS linear-gradient той же шкалы (легенда ≡ карта). */
export function noiseScaleCssGradient(): string {
  const lo = FIRST_UPPER_DB - STEP_DB;
  const hi = FIRST_UPPER_DB + (NOISE_CLASSES.length - 1) * STEP_DB;
  const stops = ANCHORS_DB.map((db, i) => {
    const [r, g, b] = DIN_45682_RGB[i]!;
    const pct = ((db - lo) / (hi - lo)) * 100;
    return `rgb(${r}, ${g}, ${b}) ${pct.toFixed(2)}%`;
  });
  return `linear-gradient(to right, ${stops.join(", ")})`;
}

/** Подписи границ легенды (60, 65, …, 105). */
export function noiseScaleTicksDb(): number[] {
  return NOISE_CLASSES.slice(1).map((c) => c.lowerDb!);
}

export function noiseScaleSpanDb(): { readonly loDb: number; readonly hiDb: number } {
  return {
    loDb: FIRST_UPPER_DB - STEP_DB,
    hiDb: FIRST_UPPER_DB + (NOISE_CLASSES.length - 1) * STEP_DB,
  };
}

export function surfaceMapToDataUrl(args: {
  nx: number;
  ny: number;
  lpDb: readonly (number | null)[];
}): string | null {
  return surfaceMapToCanvas(args)?.toDataURL("image/png") ?? null;
}

/** Same bitmap as surfaceMapToDataUrl, without PNG encode (live redraw while dragging). */
export function surfaceMapToCanvas(args: {
  nx: number;
  ny: number;
  lpDb: readonly (number | null)[];
}): HTMLCanvasElement | null {
  const { nx, ny, lpDb } = args;
  if (nx < 1 || ny < 1 || lpDb.length < nx * ny) return null;
  if (typeof document === "undefined") return null;
  if (!lpDb.some((v) => v !== null && Number.isFinite(v))) return null;
  // Native cell bitmap, then upsample with smoothing for less "LEGO" on phone.
  const src = document.createElement("canvas");
  src.width = nx;
  src.height = ny;
  const sctx = src.getContext("2d");
  if (!sctx) return null;
  const img = sctx.createImageData(nx, ny);
  for (let j = 0; j < ny; j++) {
    for (let i = 0; i < nx; i++) {
      // row 0 = min Y (project); canvas y grows down → flip
      const srcRow = ny - 1 - j;
      const lp = lpDb[srcRow * nx + i] ?? null;
      const [r, g, b, a] = lpToRgba(lp);
      const o = (j * nx + i) * 4;
      img.data[o] = r;
      img.data[o + 1] = g;
      img.data[o + 2] = b;
      img.data[o + 3] = a;
    }
  }
  sctx.putImageData(img, 0, 0);
  const up = 4;
  const canvas = document.createElement("canvas");
  canvas.width = nx * up;
  canvas.height = ny * up;
  const ctx = canvas.getContext("2d");
  if (!ctx) return null;
  ctx.imageSmoothingEnabled = true;
  ctx.imageSmoothingQuality = "high";
  ctx.drawImage(src, 0, 0, canvas.width, canvas.height);
  return canvas;
}
