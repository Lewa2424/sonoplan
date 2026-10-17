/**
 * Суммарный уровень звуковой мощности LwA источника по его октавному спектру Lw.
 * Спектр хранится невзвешенным (дБ re 1 пВт); A-коррекция применяется один раз
 * к каждой полосе, затем сумма по энергии.
 */
import { aWeightingDb } from "./aWeighting.js";
import type { OctaveBandLevel } from "./types.js";

function requireAWeighting(bandHz: number): number {
  const a = aWeightingDb(bandHz);
  if (a === null) {
    throw new RangeError(`A-weighting unknown for ${bandHz} Hz (not a nominal band)`);
  }
  return a;
}

/** LwA, дБА re 1 пВт; null — в спектре нет ни одной известной полосы. */
export function totalLwA(spectrum: readonly OctaveBandLevel[]): number | null {
  let energy = 0;
  let known = 0;
  for (const band of spectrum) {
    const lw = band.level.value;
    if (lw === null || !Number.isFinite(lw)) continue;
    energy += 10 ** ((lw + requireAWeighting(band.bandHz)) / 10);
    known += 1;
  }
  return known > 0 ? 10 * Math.log10(energy) : null;
}

/**
 * Ровный спектр Lw (одинаковый уровень в каждой полосе), суммарный LwA которого
 * равен `lwA`. Для октав 63…8000 Гц уровень полосы = LwA − 7,0 дБ.
 */
export function flatLwSpectrumForLwA(
  lwA: number,
  bandsHz: readonly number[],
): OctaveBandLevel[] {
  if (bandsHz.length === 0) return [];
  let weightEnergy = 0;
  for (const hz of bandsHz) weightEnergy += 10 ** (requireAWeighting(hz) / 10);
  const perBand = lwA - 10 * Math.log10(weightEnergy);
  return bandsHz.map((bandHz) => ({
    bandHz,
    level: { value: perBand, unit: "dB" as const },
  }));
}
