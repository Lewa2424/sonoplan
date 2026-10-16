/** Палитра Lp для карты сечения (как в UX-примере). null → прозрачный. */
export function lpToRgba(lpDb: number | null | undefined): [number, number, number, number] {
  if (lpDb === null || lpDb === undefined || !Number.isFinite(lpDb)) {
    return [0, 0, 0, 0];
  }
  if (lpDb > 100) return [220, 38, 38, 180];
  if (lpDb >= 90) return [234, 88, 12, 160];
  if (lpDb >= 80) return [234, 179, 8, 140];
  return [34, 197, 94, 120];
}

export function surfaceMapToDataUrl(args: {
  nx: number;
  ny: number;
  lpDb: readonly (number | null)[];
}): string | null {
  const { nx, ny, lpDb } = args;
  if (nx < 1 || ny < 1 || lpDb.length < nx * ny) return null;
  if (typeof document === "undefined") return null;
  const canvas = document.createElement("canvas");
  canvas.width = nx;
  canvas.height = ny;
  const ctx = canvas.getContext("2d");
  if (!ctx) return null;
  const img = ctx.createImageData(nx, ny);
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
  ctx.putImageData(img, 0, 0);
  return canvas.toDataURL("image/png");
}
