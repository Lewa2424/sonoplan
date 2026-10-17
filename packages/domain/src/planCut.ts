/**
 * Высота горизонтального среза карты — та же, что у сечения SPPS
 * (engine/adapter/sonoplan_adapter/export_revision.py: compact_export_payload,
 * _coupe_z_away_from_sources, build_config_xml). Оценка и SPPS должны
 * показывать одну и ту же плоскость; правило менять только в обоих местах
 * (паритет закреплён одинаковыми кейсами в тестах TS и Python).
 */
import type { ModelSnapshot, Workplace } from "./types.js";

const DEFAULT_RECEIVER_Z_M = 1.5;
/** Сечение не должно лежать в плоскости источника — SPPS регистрирует пересечения. */
const MIN_SOURCE_SEPARATION_M = 0.35;

/** Высота приёмника рабочего места над полом, как в экспорте SPPS. */
export function workplaceReceiverZ(w: Workplace): number {
  const z = w.position.z;
  if (z > 0.05) return z;
  const h = w.receiverHeightM.value;
  return h !== null && Number.isFinite(h) && h !== 0 ? h : DEFAULT_RECEIVER_Z_M;
}

function cutZAwayFromSources(
  preferredZ: number,
  sourceZs: readonly number[],
  heightM: number,
): number {
  const lo = 0.15;
  const hi = Math.max(heightM - 0.15, 0.2);
  const clamp = (z: number) => Math.min(Math.max(z, lo), hi);
  const preferred = clamp(preferredZ);
  const sep = MIN_SOURCE_SEPARATION_M;
  const candidates = [
    preferred,
    preferred - sep,
    preferred + sep,
    preferred - 2 * sep,
    preferred + 2 * sep,
    1.2,
    1.8,
    lo + 0.1,
    hi - 0.1,
  ];
  for (const z of candidates) {
    const zc = clamp(z);
    if (sourceZs.length === 0) return zc;
    if (sourceZs.every((sz) => Math.abs(zc - sz) >= sep)) return zc;
  }
  const lowest = sourceZs.length > 0 ? Math.min(...sourceZs) : preferred;
  return clamp(lowest - sep);
}

/** Высота среза карты, м; null — высота помещения неизвестна. */
export function planCutHeightM(model: ModelSnapshot): number | null {
  const height = model.rooms[0]?.heightM.value ?? null;
  if (height === null || !Number.isFinite(height) || height <= 0) return null;
  const wpZs = model.workplaces.map(workplaceReceiverZ);
  const preferred =
    wpZs.length > 0
      ? wpZs.reduce((a, b) => a + b, 0) / wpZs.length
      : DEFAULT_RECEIVER_Z_M;
  const sourceZs = model.sources.map((s) => s.position.z);
  const first = cutZAwayFromSources(preferred, sourceZs, height);
  const second = cutZAwayFromSources(first, sourceZs, height);
  return Math.min(Math.max(second, 0.1), height - 0.05);
}
