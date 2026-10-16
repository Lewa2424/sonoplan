/** Палитра карты сечения: автошкала по min/max ячеек с энергией (не фиксированные 80/90/100). */

export type LpColorScale = {
  readonly minDb: number;
  readonly maxDb: number;
};

/** Continuous teal→yellow→red; null/empty → transparent. */
export function lpToRgba(
  lpDb: number | null | undefined,
  scale: LpColorScale,
): [number, number, number, number] {
  if (lpDb === null || lpDb === undefined || !Number.isFinite(lpDb)) {
    return [0, 0, 0, 0];
  }
  const span = scale.maxDb - scale.minDb;
  const t =
    span < 0.5
      ? 0.5
      : Math.min(1, Math.max(0, (lpDb - scale.minDb) / span));
  const [r, g, b] = sampleRamp(t);
  const a = 110 + Math.round(70 * t);
  return [r, g, b, a];
}

/** Stops: quiet (teal) → mid (yellow) → loud (red). Not absolute dB thresholds. */
const RAMP: readonly (readonly [number, number, number, number])[] = [
  [0, 20, 120, 140],
  [0.35, 34, 180, 140],
  [0.55, 234, 179, 8],
  [0.75, 234, 88, 12],
  [1, 220, 38, 38],
];

function sampleRamp(t: number): [number, number, number] {
  let i = 0;
  while (i < RAMP.length - 2 && t > RAMP[i + 1]![0]) i += 1;
  const a = RAMP[i]!;
  const b = RAMP[i + 1]!;
  const u = (t - a[0]) / Math.max(b[0] - a[0], 1e-9);
  return [
    Math.round(a[1] + (b[1] - a[1]) * u),
    Math.round(a[2] + (b[2] - a[2]) * u),
    Math.round(a[3] + (b[3] - a[3]) * u),
  ];
}

export function computeLpScale(
  lpDb: readonly (number | null)[],
): LpColorScale | null {
  let minDb = Infinity;
  let maxDb = -Infinity;
  for (const v of lpDb) {
    if (v === null || v === undefined || !Number.isFinite(v)) continue;
    if (v < minDb) minDb = v;
    if (v > maxDb) maxDb = v;
  }
  if (!Number.isFinite(minDb) || !Number.isFinite(maxDb)) return null;
  if (maxDb - minDb < 0.5) {
    return { minDb: minDb - 0.25, maxDb: maxDb + 0.25 };
  }
  return { minDb, maxDb };
}

export function formatLpScaleLegend(scale: LpColorScale): string {
  const a = scale.minDb.toFixed(1);
  const b = scale.maxDb.toFixed(1);
  return `${a}…${b} дБ (авто по карте): тихо → громко`;
}

export function surfaceMapToDataUrl(args: {
  nx: number;
  ny: number;
  lpDb: readonly (number | null)[];
  scale?: LpColorScale | null;
}): string | null {
  return surfaceMapToCanvas(args)?.toDataURL("image/png") ?? null;
}

/** Same bitmap as surfaceMapToDataUrl, without PNG encode (live redraw while dragging). */
export function surfaceMapToCanvas(args: {
  nx: number;
  ny: number;
  lpDb: readonly (number | null)[];
  scale?: LpColorScale | null;
}): HTMLCanvasElement | null {
  const { nx, ny, lpDb } = args;
  if (nx < 1 || ny < 1 || lpDb.length < nx * ny) return null;
  if (typeof document === "undefined") return null;
  const scale = args.scale ?? computeLpScale(lpDb);
  if (!scale) return null;
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
      const [r, g, b, a] = lpToRgba(lp, scale);
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
  ctx.drawImage(src, 0, 0, canvas.width, canvas.height);
  return canvas;
}
