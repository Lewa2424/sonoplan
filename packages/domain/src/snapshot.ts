/**
 * Канонический JSON и snapshotHash ревизии.
 * Хеш зависит только от акустической модели (не от имени проекта / камеры).
 */

import { sha256Hex } from "./sha256.js";
import type { ModelSnapshot } from "./types.js";

/** Рекурсивная сортировка ключей объектов для стабильной сериализации. */
export function sortKeysDeep(value: unknown): unknown {
  if (value === null || typeof value !== "object") {
    return value;
  }
  if (Array.isArray(value)) {
    return value.map(sortKeysDeep);
  }
  const obj = value as Record<string, unknown>;
  const keys = Object.keys(obj).sort();
  const out: Record<string, unknown> = {};
  for (const key of keys) {
    out[key] = sortKeysDeep(obj[key]);
  }
  return out;
}

/** Канонический JSON: отсортированные ключи, без лишних пробелов. */
export function canonicalJson(value: unknown): string {
  return JSON.stringify(sortKeysDeep(value));
}

/** Полезная нагрузка хеша (без метаданных проекта / UI). */
export function snapshotHashPayload(snapshot: ModelSnapshot): unknown {
  return {
    schemaVersion: snapshot.schemaVersion,
    rooms: snapshot.rooms,
    sources: snapshot.sources,
    workplaces: snapshot.workplaces,
    materials: snapshot.materials,
    solids: snapshot.solids,
  };
}

/**
 * SHA-256 hex от канонического JSON снимка модели.
 * Не включает имя проекта, камеру и UI-состояние.
 */
export function computeSnapshotHash(snapshot: ModelSnapshot): string {
  return sha256Hex(canonicalJson(snapshotHashPayload(snapshot)));
}

/** Сериализация снимка без потерь (round-trip через JSON). */
export function serializeModelSnapshot(snapshot: ModelSnapshot): string {
  return canonicalJson(snapshot);
}

export function parseModelSnapshot(json: string): ModelSnapshot {
  const parsed: unknown = JSON.parse(json);
  if (parsed === null || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error("ModelSnapshot must be a JSON object");
  }
  const obj = parsed as Record<string, unknown>;
  if (obj["schemaVersion"] !== "1.0") {
    throw new Error(`Unsupported schemaVersion: ${String(obj["schemaVersion"])}`);
  }
  return parsed as ModelSnapshot;
}
