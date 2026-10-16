/**
 * Единицы и подписи величин (всегда рядом с числами в UI).
 * Lw ≠ Lp; дБ только по энергии.
 */

export type LengthUnit = "m" | "mm";
export type LevelUnit = "dB" | "dBA";
export type PowerLevelUnit = "dB"; // Lw — уровень звуковой мощности
export type PressureLevelUnit = "dB" | "dBA"; // Lp — уровень звукового давления

export interface Quantity<TUnit extends string> {
  readonly value: number | null;
  readonly unit: TUnit;
  /** Причина null; обязательна, если value === null (DAT-001: null ≠ 0). */
  readonly nullReason?: string | null;
}

export function finiteOrNull(
  value: number,
  reasonIfInvalid = "non_finite",
): { value: number | null; nullReason: string | null } {
  if (!Number.isFinite(value)) {
    return { value: null, nullReason: reasonIfInvalid };
  }
  return { value, nullReason: null };
}

/** Неизвестное значение: null + причина, не 0. */
export function unknownQuantity<TUnit extends string>(
  unit: TUnit,
  reason: string,
): Quantity<TUnit> {
  return { value: null, unit, nullReason: reason };
}
