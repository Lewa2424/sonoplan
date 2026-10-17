import {
  PROJECT_SCHEMA_VERSION,
  ROOM_SURFACE_KINDS,
  createUuid,
  flatLwSpectrumForLwA,
  migrateModelSnapshot,
  type ModelSnapshot,
  type OctaveBandLevel,
  type ProjectDraft,
  type Room,
  type RoomSurfaceKind,
  type SolidObstacle,
  type Source,
  type Workplace,
} from "@sonoplan/domain";
import { rectangleContour } from "./contourHelpers";
import {
  DEFAULT_SURFACE_MATERIAL_KEYS,
  MATERIAL_CATALOG_VERSION,
  createMaterialVersionFromCatalog,
} from "./materialCatalog";
import {
  equipmentByKey,
  lwSpectrumForEquipment,
  solidByKind,
  type SolidKind,
} from "./equipmentCatalog";

/** Стандартные октавные полосы для упрощённого ввода Lw. */
export const STANDARD_BANDS_HZ = [
  63, 125, 250, 500, 1000, 2000, 4000, 8000,
] as const;

/**
 * Ровный октавный спектр Lw (дБ re 1 pW, не Lp) с заданным суммарным LwA, дБА.
 * Каждая из 8 октав = LwA − 7,0 дБ.
 */
export function flatLwSpectrumFromLwA(lwADb: number): OctaveBandLevel[] {
  return flatLwSpectrumForLwA(lwADb, STANDARD_BANDS_HZ);
}

/** Типовой источник без паспорта: LwA 97 дБА (≈90 дБ в каждой октаве). */
export const DEFAULT_SOURCE_LWA_DB = 97;

export function createEmptyModel(): ModelSnapshot {
  return {
    schemaVersion: PROJECT_SCHEMA_VERSION,
    rooms: [],
    sources: [],
    workplaces: [],
    materials: [],
    solids: [],
  };
}

export function createDefaultWorkshopRoom(
  widthM = 20,
  depthM = 12,
  heightM = 6,
): Room {
  return {
    id: createUuid(),
    floorContour: rectangleContour(widthM, depthM),
    heightM: { value: heightM, unit: "m" },
    surfaceMaterials: { floor: null, walls: null, ceiling: null },
    materialNullReason: "not_assigned_mvp",
  };
}

export function createSourceAt(
  x: number,
  y: number,
  z: number,
  lwADb = DEFAULT_SOURCE_LWA_DB,
  name = "Источник",
): Source {
  return {
    id: createUuid(),
    name,
    position: { x, y, z },
    powerSpectrumLw: flatLwSpectrumFromLwA(lwADb),
    directivityId: null,
    weight: null,
    weightNullReason: "not_used_mvp",
  };
}

export function createWorkplaceAt(
  x: number,
  y: number,
  receiverHeightM = 1.5,
  name = "Рабочее место",
): Workplace {
  return {
    id: createUuid(),
    name,
    kind: "point",
    position: { x, y, z: receiverHeightM },
    receiverHeightM: { value: receiverHeightM, unit: "m" },
    scheduleId: null,
  };
}

export function createEquipmentSourceAt(
  x: number,
  y: number,
  z: number,
  catalogKey: string,
): Source {
  const { name, spectrum } = lwSpectrumForEquipment(catalogKey);
  return {
    id: createUuid(),
    name,
    position: { x, y, z },
    powerSpectrumLw: spectrum,
    directivityId: null,
    weight: null,
    weightNullReason: "not_used_mvp",
  };
}

/** Прямоугольный solid (стеллаж / шкаф / перегородка) с центром (cx, cy). */
export function createSolidAt(
  cx: number,
  cy: number,
  kind: SolidKind,
): SolidObstacle {
  const cat = solidByKind(kind);
  const hw = cat.defaultWidthM / 2;
  const hd = cat.defaultDepthM / 2;
  return {
    id: createUuid(),
    name: cat.nameRu,
    floorContour: [
      { x: cx - hw, y: cy - hd },
      { x: cx + hw, y: cy - hd },
      { x: cx + hw, y: cy + hd },
      { x: cx - hw, y: cy + hd },
      { x: cx - hw, y: cy - hd },
    ],
    baseZM: 0,
    heightM: { value: cat.defaultHeightM, unit: "m" },
  };
}

/**
 * Назначить материал каталога группе ограждений первого помещения.
 * Версия того же ключа текущего каталога переиспользуется; материалы, на которые
 * больше не ссылается ни одна поверхность, удаляются из модели.
 */
export function assignSurfaceMaterial(
  model: ModelSnapshot,
  surface: RoomSurfaceKind,
  catalogKey: string,
): ModelSnapshot {
  const room = model.rooms[0];
  if (!room) return model;
  const existing = model.materials.find(
    (m) => m.catalogKey === catalogKey && m.version === MATERIAL_CATALOG_VERSION,
  );
  const mat = existing ?? createMaterialVersionFromCatalog(catalogKey);
  const surfaceMaterials = { ...room.surfaceMaterials, [surface]: mat.id };
  const used = new Set(Object.values(surfaceMaterials));
  const materials = model.materials.filter((m) => used.has(m.id));
  return {
    ...model,
    materials: existing ? materials : [...materials, mat],
    rooms: [
      { ...room, surfaceMaterials, materialNullReason: null },
      ...model.rooms.slice(1),
    ],
  };
}

/** Поверхности без материала (или с битой ссылкой) получают материал по умолчанию. */
export function ensureRoomSurfaceMaterials(model: ModelSnapshot): ModelSnapshot {
  let next = model;
  for (const surface of ROOM_SURFACE_KINDS) {
    const room = next.rooms[0];
    if (!room) return next;
    const id = room.surfaceMaterials[surface];
    if (id !== null && next.materials.some((m) => m.id === id)) continue;
    next = assignSurfaceMaterial(next, surface, DEFAULT_SURFACE_MATERIAL_KEYS[surface]);
  }
  return next;
}

export function workplaceNearEquipment(
  x: number,
  y: number,
  catalogKey: string,
): Workplace {
  const entry = equipmentByKey(catalogKey);
  const offset = entry?.workplaceOffsetM ?? 1.0;
  return createWorkplaceAt(x + offset, y, 1.5, "Рабочее место");
}

export function createOfflineDraft(name: string): ProjectDraft {
  const room: Room = createDefaultWorkshopRoom();
  return {
    schemaVersion: PROJECT_SCHEMA_VERSION,
    name,
    model: ensureRoomSurfaceMaterials({ ...createEmptyModel(), rooms: [room] }),
  };
}

/**
 * Draft body с сервера → текущая схема. Черновик 1.0 мигрирует в памяти;
 * на сервере он остаётся 1.0 до следующего сохранения.
 */
export function parseDraftBody(raw: unknown): ProjectDraft {
  if (!raw || typeof raw !== "object") {
    throw new Error("Invalid draft body");
  }
  const body = raw as Record<string, unknown>;
  const modelRaw = body.model;
  const model =
    modelRaw && typeof modelRaw === "object"
      ? migrateModelSnapshot({
          schemaVersion: body.schemaVersion,
          ...(modelRaw as Record<string, unknown>),
        })
      : createEmptyModel();
  return {
    schemaVersion: PROJECT_SCHEMA_VERSION,
    name: typeof body.name === "string" ? body.name : "Без имени",
    model,
  };
}
