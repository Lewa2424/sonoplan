import {
  PROJECT_SCHEMA_VERSION,
  createUuid,
  type ModelSnapshot,
  type OctaveBandLevel,
  type ProjectDraft,
  type Room,
  type Source,
  type Workplace,
} from "@sonoplan/domain";
import { rectangleContour } from "./contourHelpers";

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

export function createOfflineDraft(name: string): ProjectDraft {
  const room = createDefaultWorkshopRoom();
  return {
    schemaVersion: PROJECT_SCHEMA_VERSION,
    name,
    model: {
      ...createEmptyModel(),
      rooms: [room],
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
