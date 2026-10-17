/**
 * Миграции документа модели между версиями схемы.
 * Ревизии в БД не переписываются: миграция применяется при чтении черновика,
 * новая версия сохраняется только следующим сохранением пользователя.
 */
import {
  LEGACY_PROJECT_SCHEMA_VERSIONS,
  PROJECT_SCHEMA_VERSION,
  type ModelSnapshot,
  type Room,
} from "./types.js";

export class UnsupportedSchemaVersionError extends Error {
  constructor(readonly schemaVersion: unknown) {
    super(`Unsupported schemaVersion: ${String(schemaVersion)}`);
    this.name = "UnsupportedSchemaVersionError";
  }
}

type JsonObject = Record<string, unknown>;

function isObject(value: unknown): value is JsonObject {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function arrayOrEmpty(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

/**
 * 1.0 → 1.1: один материал помещения становится материалом пола, стен и потолка.
 * Как экспорт 1.0 и оценка 1.0, при пустой/битой ссылке берётся первый материал
 * модели — так расчёт мигрированной модели совпадает с прежним.
 */
function migrateRoom10(room: JsonObject, materials: unknown[]): JsonObject {
  const { materialVersionId, ...rest } = room;
  const ids = new Set(
    materials.filter(isObject).map((m) => m["id"]).filter((id) => typeof id === "string"),
  );
  const first = materials.find(isObject)?.["id"];
  const resolved =
    typeof materialVersionId === "string" && ids.has(materialVersionId)
      ? materialVersionId
      : typeof first === "string"
        ? first
        : null;
  return {
    ...rest,
    surfaceMaterials: { floor: resolved, walls: resolved, ceiling: resolved },
  };
}

/** Неполные surfaceMaterials 1.1 → явный null (виден в validate), не падение. */
function normalizeRoom11(room: JsonObject): JsonObject {
  const raw = isObject(room["surfaceMaterials"]) ? room["surfaceMaterials"] : {};
  const pick = (k: string) => (typeof raw[k] === "string" ? raw[k] : null);
  return {
    ...room,
    surfaceMaterials: { floor: pick("floor"), walls: pick("walls"), ceiling: pick("ceiling") },
  };
}

/** Привести снимок модели любой поддерживаемой версии к текущей. */
export function migrateModelSnapshot(raw: unknown): ModelSnapshot {
  if (!isObject(raw)) {
    throw new Error("ModelSnapshot must be a JSON object");
  }
  // Документы без версии появились до введения schemaVersion — это 1.0.
  const version = raw["schemaVersion"] ?? "1.0";
  const materials = arrayOrEmpty(raw["materials"]);
  let rooms = arrayOrEmpty(raw["rooms"]);
  if ((LEGACY_PROJECT_SCHEMA_VERSIONS as readonly unknown[]).includes(version)) {
    rooms = rooms.map((r) => (isObject(r) ? migrateRoom10(r, materials) : r));
  } else if (version !== PROJECT_SCHEMA_VERSION) {
    throw new UnsupportedSchemaVersionError(version);
  }
  rooms = rooms.map((r) => (isObject(r) ? normalizeRoom11(r) : r));
  return {
    schemaVersion: PROJECT_SCHEMA_VERSION,
    rooms: rooms as Room[],
    sources: arrayOrEmpty(raw["sources"]) as ModelSnapshot["sources"],
    workplaces: arrayOrEmpty(raw["workplaces"]) as ModelSnapshot["workplaces"],
    materials: materials as ModelSnapshot["materials"],
    solids: arrayOrEmpty(raw["solids"]) as ModelSnapshot["solids"],
  };
}
