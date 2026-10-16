import {
  PROJECT_SCHEMA_VERSION,
  createUuid,
  type ModelSnapshot,
  type OctaveBandLevel,
  type ProjectDraft,
  type Room,
  type SolidObstacle,
  type Source,
  type Workplace,
} from "@sonoplan/domain";
import { rectangleContour } from "./contourHelpers";
import {
  createMaterialVersionFromCatalog,
  materialByKey,
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

/** quantity: sound_power (Lw), unit dB re 1 pW — не Lp. */
export function uniformLwSpectrum(levelDb: number): OctaveBandLevel[] {
  return STANDARD_BANDS_HZ.map((bandHz) => ({
    bandHz,
    level: { value: levelDb, unit: "dB" as const },
  }));
}

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
    materialVersionId: null,
    materialNullReason: "not_assigned_mvp",
  };
}

export function createSourceAt(
  x: number,
  y: number,
  z: number,
  lwDb = 90,
  name = "Источник",
): Source {
  return {
    id: createUuid(),
    name,
    position: { x, y, z },
    powerSpectrumLw: uniformLwSpectrum(lwDb),
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

export function createDefaultMaterial(): ReturnType<
  typeof createMaterialVersionFromCatalog
> {
  return createMaterialVersionFromCatalog("concrete");
}

export function ensureRoomMaterial(
  model: ModelSnapshot,
  catalogKey = "concrete",
): ModelSnapshot {
  const room = model.rooms[0];
  if (!room) return model;
  if (room.materialVersionId && model.materials.length > 0) {
    return model;
  }
  const mat = createMaterialVersionFromCatalog(
    materialByKey(catalogKey)?.catalogKey ?? "concrete",
  );
  return {
    ...model,
    materials: [mat, ...model.materials.filter((m) => m.id !== mat.id)],
    rooms: [
      {
        ...room,
        materialVersionId: mat.id,
        materialNullReason: null,
      },
    ],
  };
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
  const mat = createDefaultMaterial();
  const room: Room = {
    ...createDefaultWorkshopRoom(),
    materialVersionId: mat.id,
    materialNullReason: null,
  };
  return {
    schemaVersion: PROJECT_SCHEMA_VERSION,
    name,
    model: {
      ...createEmptyModel(),
      rooms: [room],
      materials: [mat],
    },
  };
}

export function parseDraftBody(raw: unknown): ProjectDraft {
  if (!raw || typeof raw !== "object") {
    throw new Error("Invalid draft body");
  }
  const body = raw as Record<string, unknown>;
  const modelRaw = body.model;
  const model =
    modelRaw && typeof modelRaw === "object"
      ? (modelRaw as ModelSnapshot)
      : createEmptyModel();
  return {
    schemaVersion:
      typeof body.schemaVersion === "string"
        ? (body.schemaVersion as ProjectDraft["schemaVersion"])
        : PROJECT_SCHEMA_VERSION,
    name: typeof body.name === "string" ? body.name : "Без имени",
    model: {
      schemaVersion: model.schemaVersion ?? PROJECT_SCHEMA_VERSION,
      rooms: model.rooms ?? [],
      sources: model.sources ?? [],
      workplaces: model.workplaces ?? [],
      materials: model.materials ?? [],
      solids: model.solids ?? [],
    },
  };
}
