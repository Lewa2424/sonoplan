import {
  isUuid,
  stripClosingDuplicate,
  validateModel,
  type FloorVertex,
  type ModelSnapshot,
  type ProjectDraft,
  type Uuid,
  type ValidationIssue,
} from "@sonoplan/domain";
import { create } from "zustand";
import { ApiError } from "../api/client";
import {
  createRevision,
  getDraft,
  patchDraft,
  validateRevision,
} from "../api/projectsApi";
import type { SolidKind } from "../model/equipmentCatalog";
import {
  createDefaultWorkshopRoom,
  createEquipmentSourceAt,
  createOfflineDraft,
  createSolidAt,
  createSourceAt,
  createWorkplaceAt,
  ensureRoomMaterial,
  parseDraftBody,
  workplaceNearEquipment,
} from "../model/factoryModel";
import { createMaterialVersionFromCatalog } from "../model/materialCatalog";
import {
  contourVertexAngles,
  ensureClosedContour,
  lShapeContour,
  rectangleContour,
  snapNearRightAngles,
} from "../model/contourHelpers";

export type ConnectionMode = "online" | "offline";
export type ToolMode = "select" | "move" | "drawPolygon";
export type SyncStatus =
  | "idle"
  | "loading"
  | "saving"
  | "saved"
  | "dirty"
  | "conflict"
  | "error"
  | "offline";

export type Selection =
  | { kind: "room"; id: string }
  | { kind: "source"; id: string }
  | { kind: "workplace"; id: string }
  | { kind: "solid"; id: string }
  | null;

/** Карта сечения SPPS (не интерполяция punctual). */
export interface PlanSurfaceMapOverlay {
  readonly jobId: string;
  readonly revisionId: string;
  readonly zM: number;
  readonly originX: number;
  readonly originY: number;
  readonly cellSizeM: number;
  readonly nx: number;
  readonly ny: number;
  /** row-major; null = нет энергии (не 0 дБ). */
  readonly lpDb: readonly (number | null)[];
}

interface LastRevisionInfo {
  revisionId: string;
  snapshotHash: string;
}

/** Lp (dB) shown on plan at workplaces after a completed job. */
export interface PlanLpOverlay {
  readonly byWorkplaceId: Readonly<Record<string, number>>;
  readonly jobId: string;
  readonly revisionId: string;
  readonly fixtureReplay: boolean;
}

interface EditorState {
  connectionMode: ConnectionMode;
  projectId: string | null;
  projectName: string;
  etag: string | null;
  model: ModelSnapshot;
  selection: Selection;
  toolMode: ToolMode;
  syncStatus: SyncStatus;
  syncMessage: string | null;
  polygonDraft: FloorVertex[];
  validationIssues: ValidationIssue[];
  lastRevision: LastRevisionInfo | null;
  planLpOverlay: PlanLpOverlay | null;
  planSurfaceMap: PlanSurfaceMapOverlay | null;
  pendingEquipmentKey: string | null;
  pendingSolidKind: SolidKind | null;
  placeWithWorkplace: boolean;
  roomWidthM: number;
  roomDepthM: number;
  roomHeightM: number;

  reset: () => void;
  openOffline: (name: string) => void;
  loadOnlineProject: (projectId: string) => Promise<void>;
  setToolMode: (mode: ToolMode) => void;
  setSelection: (sel: Selection) => void;
  setRoomDimensions: (w: number, d: number, h: number) => void;
  applyRectangleRoom: () => void;
  applyLShapeRoom: () => void;
  snapRoomRightAngles: () => void;
  beginPolygon: () => void;
  addPolygonVertex: (x: number, y: number) => void;
  updatePolygonDraftVertex: (index: number, x: number, y: number) => void;
  finishPolygon: () => void;
  cancelPolygon: () => void;
  updateRoomVertex: (index: number, x: number, y: number) => void;
  addSource: (x: number, y: number) => void;
  addWorkplace: (x: number, y: number) => void;
  addEquipmentAt: (x: number, y: number, catalogKey: string) => void;
  addSolidAt: (x: number, y: number, kind: SolidKind) => void;
  setPendingEquipment: (catalogKey: string | null) => void;
  setPendingSolid: (kind: SolidKind | null) => void;
  setPlaceWithWorkplace: (v: boolean) => void;
  setRoomMaterial: (catalogKey: string) => void;
  updateSelectedName: (name: string) => void;
  updateSourceLw: (levelDb: number) => void;
  updateSourcePosition: (x: number, y: number, z: number) => void;
  updateWorkplacePosition: (x: number, y: number, z: number) => void;
  updateSolidHeight: (heightM: number) => void;
  moveSelectedBy: (dx: number, dy: number) => void;
  runValidate: () => Promise<void>;
  commitRevision: () => Promise<void>;
  saveDraft: () => Promise<void>;
  reloadDraft: () => Promise<void>;
  markDirty: () => void;
  setPlanLpOverlay: (overlay: PlanLpOverlay | null) => void;
  setPlanSurfaceMap: (overlay: PlanSurfaceMapOverlay | null) => void;
  /**
   * Map punctual receivers (order) → workplaces (order).
   * Honest for fixture_replay: same numbers as CI table, assigned by index.
   */
  applyPunctualLpToWorkplaces: (args: {
    jobId: string;
    revisionId: string;
    fixtureReplay: boolean;
    punctual: readonly {
      lpDbGlobal?: number | null;
      receiverId?: string | null;
    }[];
  }) => void;
  applySurfaceMapFromManifest: (args: {
    jobId: string;
    revisionId: string;
    grid: {
      originX: number;
      originY: number;
      cellSizeM: number;
      nx: number;
      ny: number;
      zM?: number;
      lpDb: readonly (number | null)[];
    };
  }) => void;
  /** Lp на плане устарели относительно черновика / другой ревизии. */
  isPlanResultStale: () => boolean;
}

const initialModel = createOfflineDraft("Новый цех").model;

function withRoom(
  model: ModelSnapshot,
  contour: FloorVertex[],
  heightM: number,
): ModelSnapshot {
  const existing = model.rooms[0];
  const room = existing
    ? {
        ...existing,
        floorContour: contour,
        heightM: { value: heightM, unit: "m" as const },
      }
    : {
        ...createDefaultWorkshopRoom(),
        floorContour: contour,
        heightM: { value: heightM, unit: "m" as const },
      };
  return { ...model, rooms: [room] };
}

function roomCenter(model: ModelSnapshot): { x: number; y: number; z: number } {
  const room = model.rooms[0];
  const h = room?.heightM.value ?? 6;
  if (!room) {
    return { x: 5, y: 5, z: Math.min(1.5, h / 2) };
  }
  const pts = room.floorContour;
  let sx = 0;
  let sy = 0;
  let n = 0;
  for (let i = 0; i < pts.length - 1; i++) {
    const p = pts[i];
    if (!p) continue;
    sx += p.x;
    sy += p.y;
    n += 1;
  }
  return {
    x: n > 0 ? sx / n : 5,
    y: n > 0 ? sy / n : 5,
    z: Math.min(1.5, (h ?? 6) / 2),
  };
}

export const useEditorStore = create<EditorState>((set, get) => ({
  connectionMode: "offline",
  projectId: null,
  projectName: "Новый цех",
  etag: null,
  model: initialModel,
  selection: null,
  toolMode: "select",
  syncStatus: "offline",
  syncMessage: null,
  polygonDraft: [],
  validationIssues: [],
  lastRevision: null,
  planLpOverlay: null,
  planSurfaceMap: null,
  pendingEquipmentKey: null,
  pendingSolidKind: null,
  placeWithWorkplace: true,
  roomWidthM: 20,
  roomDepthM: 12,
  roomHeightM: 6,

  reset: () =>
    set({
      connectionMode: "offline",
      projectId: null,
      projectName: "Новый цех",
      etag: null,
      model: createOfflineDraft("Новый цех").model,
      selection: null,
      toolMode: "select",
      syncStatus: "offline",
      syncMessage: null,
      polygonDraft: [],
      validationIssues: [],
      lastRevision: null,
      planLpOverlay: null,
      planSurfaceMap: null,
      pendingEquipmentKey: null,
      pendingSolidKind: null,
      placeWithWorkplace: true,
      roomWidthM: 20,
      roomDepthM: 12,
      roomHeightM: 6,
    }),

  openOffline: (name) => {
    const draft = createOfflineDraft(name);
    set({
      connectionMode: "offline",
      projectId: `offline-${crypto.randomUUID()}`,
      projectName: draft.name,
      etag: null,
      model: draft.model,
      selection: draft.model.rooms[0]
        ? { kind: "room", id: draft.model.rooms[0].id }
        : null,
      toolMode: "select",
      syncStatus: "offline",
      syncMessage: "Локальный черновик (offline) — без синхронизации API",
      polygonDraft: [],
      validationIssues: [],
      lastRevision: null,
      planLpOverlay: null,
      planSurfaceMap: null,
      pendingEquipmentKey: null,
      pendingSolidKind: null,
      placeWithWorkplace: true,
      roomWidthM: 20,
      roomDepthM: 12,
      roomHeightM: 6,
    });
  },

  loadOnlineProject: async (projectId) => {
    set({ syncStatus: "loading", syncMessage: null });
    try {
      const { draft, etag } = await getDraft(projectId);
      const body = parseDraftBody(draft.body);
      let model = body.model;
      if (model.rooms.length === 0) {
        model = { ...model, rooms: [createDefaultWorkshopRoom()] };
      }
      model = ensureRoomMaterial(model);
      const room = model.rooms[0];
      set({
        connectionMode: "online",
        projectId,
        projectName: body.name,
        etag,
        model,
        selection: room ? { kind: "room", id: room.id } : null,
        toolMode: "select",
        syncStatus: "saved",
        syncMessage: null,
        polygonDraft: [],
        validationIssues: [],
        lastRevision: null,
        planLpOverlay: null,
        planSurfaceMap: null,
        pendingEquipmentKey: null,
        pendingSolidKind: null,
        roomHeightM: room?.heightM.value ?? 6,
      });
    } catch (err) {
      set({
        syncStatus: "error",
        syncMessage:
          err instanceof Error ? err.message : "Не удалось загрузить draft",
      });
      throw err;
    }
  },

  setToolMode: (mode) => set({ toolMode: mode }),
  setSelection: (sel) => set({ selection: sel }),

  setRoomDimensions: (w, d, h) =>
    set({ roomWidthM: w, roomDepthM: d, roomHeightM: h }),

  markDirty: () => {
    const { connectionMode, syncStatus } = get();
    if (connectionMode === "offline") {
      set({ syncStatus: "offline" });
      return;
    }
    if (syncStatus !== "conflict") {
      set({ syncStatus: "dirty" });
    }
  },

  applyRectangleRoom: () => {
    const { roomWidthM, roomDepthM, roomHeightM, model } = get();
    const contour = rectangleContour(roomWidthM, roomDepthM);
    const next = withRoom(model, contour, roomHeightM);
    set({
      model: next,
      selection: next.rooms[0]
        ? { kind: "room", id: next.rooms[0].id }
        : null,
    });
    get().markDirty();
  },

  applyLShapeRoom: () => {
    const { roomWidthM, roomDepthM, roomHeightM, model } = get();
    const cutW = Math.min(roomWidthM * 0.4, roomWidthM - 1);
    const cutD = Math.min(roomDepthM * 0.4, roomDepthM - 1);
    const contour = lShapeContour(roomWidthM, roomDepthM, cutW, cutD);
    const next = withRoom(model, contour, roomHeightM);
    set({
      model: next,
      selection: next.rooms[0]
        ? { kind: "room", id: next.rooms[0].id }
        : null,
    });
    get().markDirty();
  },

  snapRoomRightAngles: () => {
    const { model, roomHeightM } = get();
    const room = model.rooms[0];
    if (!room) return;
    const before = room.floorContour;
    const nearRight = contourVertexAngles(before).filter(
      (a) => a.nearRightAngle,
    ).length;
    const contour = snapNearRightAngles(before);
    const changed = JSON.stringify(before) !== JSON.stringify(contour);
    const next = withRoom(model, contour, roomHeightM);
    set({
      model: next,
      selection: next.rooms[0]
        ? { kind: "room", id: next.rooms[0].id }
        : null,
      syncMessage: changed
        ? `Выровнено: стены ≈оси и углы 90±5° (${nearRight} углов)`
        : nearRight > 0
          ? "Углы уже в пределах 90±5° — геометрия без изменений"
          : "Нет углов/рёбер в диапазоне 90±5°",
    });
    if (changed) get().markDirty();
  },

  beginPolygon: () =>
    set({ toolMode: "drawPolygon", polygonDraft: [], selection: null }),

  addPolygonVertex: (x, y) =>
    set((s) => ({ polygonDraft: [...s.polygonDraft, { x, y }] })),

  updatePolygonDraftVertex: (index, x, y) =>
    set((s) => {
      if (index < 0 || index >= s.polygonDraft.length) return s;
      const polygonDraft = s.polygonDraft.map((v, i) =>
        i === index ? { x, y } : v,
      );
      return { polygonDraft };
    }),

  updateRoomVertex: (index, x, y) => {
    const { model, roomHeightM } = get();
    const room = model.rooms[0];
    if (!room) return;
    const unique = stripClosingDuplicate(room.floorContour);
    if (index < 0 || index >= unique.length) return;
    const nextUnique = unique.map((v, i) => (i === index ? { x, y } : v));
    // Auto-stick corners within 90±5° after each vertex move.
    const contour = snapNearRightAngles(ensureClosedContour(nextUnique));
    const next = withRoom(model, contour, roomHeightM);
    set({ model: next });
    get().markDirty();
  },

  finishPolygon: () => {
    const { polygonDraft, roomHeightM, model } = get();
    if (polygonDraft.length < 3) {
      set({
        syncMessage: "Многоугольник: нужно ≥3 вершины",
        toolMode: "select",
        polygonDraft: [],
      });
      return;
    }
    try {
      const closed = ensureClosedContour(polygonDraft);
      const nearRight = contourVertexAngles(closed).filter((a) => a.nearRightAngle)
        .length;
      const contour = snapNearRightAngles(closed);
      const next = withRoom(model, contour, roomHeightM);
      set({
        model: next,
        toolMode: "select",
        polygonDraft: [],
        selection: next.rooms[0]
          ? { kind: "room", id: next.rooms[0].id }
          : null,
        syncMessage:
          nearRight > 0
            ? `Контур сохранён: ${nearRight} угол(а) ≈90° выровнены в 90°`
            : "Контур сохранён",
      });
      get().markDirty();
    } catch (err) {
      set({
        syncMessage: err instanceof Error ? err.message : "Ошибка контура",
        toolMode: "select",
        polygonDraft: [],
      });
    }
  },

  cancelPolygon: () =>
    set({ toolMode: "select", polygonDraft: [], syncMessage: null }),

  addSource: (x, y) => {
    const { model } = get();
    const z = roomCenter(model).z;
    const source = createSourceAt(x, y, z);
    const next = { ...model, sources: [...model.sources, source] };
    set({
      model: next,
      selection: { kind: "source", id: source.id },
      toolMode: "select",
    });
    get().markDirty();
  },

  addWorkplace: (x, y) => {
    const { model } = get();
    const wp = createWorkplaceAt(x, y);
    const next = { ...model, workplaces: [...model.workplaces, wp] };
    set({
      model: next,
      selection: { kind: "workplace", id: wp.id },
      toolMode: "select",
    });
    get().markDirty();
  },

  addEquipmentAt: (x, y, catalogKey) => {
    const { model, placeWithWorkplace } = get();
    const z = roomCenter(model).z;
    const source = createEquipmentSourceAt(x, y, z, catalogKey);
    let workplaces = [...model.workplaces];
    if (placeWithWorkplace) {
      workplaces = [...workplaces, workplaceNearEquipment(x, y, catalogKey)];
    }
    const next = {
      ...model,
      sources: [...model.sources, source],
      workplaces,
    };
    set({
      model: next,
      selection: { kind: "source", id: source.id },
      toolMode: "select",
      pendingEquipmentKey: null,
    });
    get().markDirty();
  },

  addSolidAt: (x, y, kind) => {
    const { model } = get();
    const solid = createSolidAt(x, y, kind);
    const next = { ...model, solids: [...model.solids, solid] };
    set({
      model: next,
      selection: { kind: "solid", id: solid.id },
      toolMode: "select",
      pendingSolidKind: null,
    });
    get().markDirty();
  },

  setPendingEquipment: (catalogKey) =>
    set({
      pendingEquipmentKey: catalogKey,
      pendingSolidKind: null,
      toolMode: "select",
    }),

  setPendingSolid: (kind) =>
    set({
      pendingSolidKind: kind,
      pendingEquipmentKey: null,
      toolMode: "select",
    }),

  setPlaceWithWorkplace: (v) => set({ placeWithWorkplace: v }),

  setRoomMaterial: (catalogKey) => {
    const { model } = get();
    const room = model.rooms[0];
    if (!room) return;
    const mat = createMaterialVersionFromCatalog(catalogKey);
    const next = {
      ...model,
      materials: [
        mat,
        ...model.materials.filter((m) => m.id !== room.materialVersionId),
      ],
      rooms: [
        {
          ...room,
          materialVersionId: mat.id,
          materialNullReason: null,
        },
      ],
    };
    set({ model: next });
    get().markDirty();
  },

  updateSelectedName: (name) => {
    const { selection, model } = get();
    if (!selection) return;
    if (selection.kind === "source") {
      set({
        model: {
          ...model,
          sources: model.sources.map((s) =>
            s.id === selection.id ? { ...s, name } : s,
          ),
        },
      });
    } else if (selection.kind === "workplace") {
      set({
        model: {
          ...model,
          workplaces: model.workplaces.map((w) =>
            w.id === selection.id ? { ...w, name } : w,
          ),
        },
      });
    } else if (selection.kind === "solid") {
      set({
        model: {
          ...model,
          solids: model.solids.map((s) =>
            s.id === selection.id ? { ...s, name } : s,
          ),
        },
      });
    }
    get().markDirty();
  },

  updateSourceLw: (levelDb) => {
    const { selection, model } = get();
    if (!selection || selection.kind !== "source") return;
    const bands = createSourceAt(0, 0, 0, levelDb).powerSpectrumLw;
    set({
      model: {
        ...model,
        sources: model.sources.map((s) =>
          s.id === selection.id ? { ...s, powerSpectrumLw: bands } : s,
        ),
      },
    });
    get().markDirty();
  },

  updateSourcePosition: (x, y, z) => {
    const { selection, model } = get();
    if (!selection || selection.kind !== "source") return;
    set({
      model: {
        ...model,
        sources: model.sources.map((s) =>
          s.id === selection.id
            ? { ...s, position: { x, y, z } }
            : s,
        ),
      },
    });
    get().markDirty();
  },

  updateWorkplacePosition: (x, y, z) => {
    const { selection, model } = get();
    if (!selection || selection.kind !== "workplace") return;
    set({
      model: {
        ...model,
        workplaces: model.workplaces.map((w) =>
          w.id === selection.id
            ? {
                ...w,
                position: { x, y, z },
                receiverHeightM: { value: z, unit: "m" },
              }
            : w,
        ),
      },
    });
    get().markDirty();
  },

  updateSolidHeight: (heightM) => {
    const { selection, model } = get();
    if (!selection || selection.kind !== "solid") return;
    set({
      model: {
        ...model,
        solids: model.solids.map((s) =>
          s.id === selection.id
            ? { ...s, heightM: { value: heightM, unit: "m" } }
            : s,
        ),
      },
    });
    get().markDirty();
  },

  moveSelectedBy: (dx, dy) => {
    const { selection, model, toolMode } = get();
    if (toolMode !== "move" || !selection) return;
    if (selection.kind === "source") {
      set({
        model: {
          ...model,
          sources: model.sources.map((s) =>
            s.id === selection.id
              ? {
                  ...s,
                  position: {
                    x: s.position.x + dx,
                    y: s.position.y + dy,
                    z: s.position.z,
                  },
                }
              : s,
          ),
        },
      });
      get().markDirty();
    } else if (selection.kind === "workplace") {
      set({
        model: {
          ...model,
          workplaces: model.workplaces.map((w) =>
            w.id === selection.id
              ? {
                  ...w,
                  position: {
                    x: w.position.x + dx,
                    y: w.position.y + dy,
                    z: w.position.z,
                  },
                }
              : w,
          ),
        },
      });
      get().markDirty();
    } else if (selection.kind === "solid") {
      set({
        model: {
          ...model,
          solids: model.solids.map((s) =>
            s.id === selection.id
              ? {
                  ...s,
                  floorContour: s.floorContour.map((p) => ({
                    x: p.x + dx,
                    y: p.y + dy,
                  })),
                }
              : s,
          ),
        },
      });
      get().markDirty();
    }
  },

  saveDraft: async () => {
    const { connectionMode, projectId, etag, model, projectName } = get();
    if (connectionMode !== "online" || !projectId || !etag) {
      set({
        syncStatus: "offline",
        syncMessage: "Offline: сохранение только локально в памяти сессии",
      });
      return;
    }
    set({ syncStatus: "saving", syncMessage: null });
    try {
      const payload: Partial<ProjectDraft> = {
        name: projectName,
        schemaVersion: model.schemaVersion,
        model,
      };
      const { etag: next } = await patchDraft(projectId, etag, payload);
      set({ etag: next, syncStatus: "saved", syncMessage: null });
    } catch (err) {
      if (err instanceof ApiError && err.status === 412) {
        set({
          syncStatus: "conflict",
          syncMessage:
            "Конфликт ETag (412): черновик изменён на сервере. Перезагрузите draft.",
        });
        return;
      }
      set({
        syncStatus: "error",
        syncMessage: err instanceof Error ? err.message : "Ошибка сохранения",
      });
    }
  },

  reloadDraft: async () => {
    const { projectId, connectionMode } = get();
    if (connectionMode !== "online" || !projectId) return;
    await get().loadOnlineProject(projectId);
  },

  runValidate: async () => {
    const { model, lastRevision, connectionMode } = get();
    const local = validateModel(model);
    let issues = [...local.errors, ...local.warnings];

    if (connectionMode === "online" && lastRevision) {
      try {
        const remote = await validateRevision(lastRevision.revisionId);
        const mapped: ValidationIssue[] = [
          ...remote.errors.map((e) => ({
            code: e.code,
            severity: "error" as const,
            message: e.message,
            path: e.path ?? undefined,
            entityId: asOptionalUuid(e.entityId),
          })),
          ...remote.warnings.map((w) => ({
            code: w.code,
            severity: "warning" as const,
            message: w.message,
            path: w.path ?? undefined,
            entityId: asOptionalUuid(w.entityId),
          })),
        ];
        issues = mapped.length > 0 ? mapped : issues;
        set({
          validationIssues: issues,
          syncMessage: remote.ok
            ? "Проверка API: ок"
            : `Проверка API: ${remote.errors.length} ошибок`,
        });
        return;
      } catch {
        // fall through to local
      }
    }

    set({
      validationIssues: issues,
      syncMessage:
        local.errors.length === 0
          ? `Проверка (domain): ок${local.warnings.length ? `, предупреждений ${local.warnings.length}` : ""}`
          : `Проверка (domain): ${local.errors.length} ошибок`,
    });
  },

  commitRevision: async () => {
    const { connectionMode, projectId, syncStatus } = get();
    if (connectionMode !== "online" || !projectId) {
      set({
        syncMessage:
          "Фиксация ревизии недоступна offline — нужен API",
      });
      return;
    }
    if (syncStatus === "dirty" || syncStatus === "conflict") {
      await get().saveDraft();
      if (get().syncStatus === "conflict" || get().syncStatus === "error") {
        return;
      }
    }
    try {
      const rev = await createRevision(projectId);
      set({
        lastRevision: {
          revisionId: rev.revisionId,
          snapshotHash: rev.snapshotHash,
        },
        planLpOverlay: null,
        planSurfaceMap: null,
        syncMessage: `Ревизия зафиксирована (${rev.revisionId.slice(0, 8)}…)`,
      });
    } catch (err) {
      set({
        syncStatus: "error",
        syncMessage:
          err instanceof Error ? err.message : "Не удалось создать ревизию",
      });
    }
  },

  setPlanLpOverlay: (overlay) => set({ planLpOverlay: overlay }),
  setPlanSurfaceMap: (overlay) => set({ planSurfaceMap: overlay }),

  isPlanResultStale: () => {
    const { planLpOverlay, planSurfaceMap, lastRevision, syncStatus } = get();
    if (syncStatus === "dirty" || syncStatus === "saving") {
      return Boolean(planLpOverlay || planSurfaceMap);
    }
    const revId = lastRevision?.revisionId;
    if (!revId) return Boolean(planLpOverlay || planSurfaceMap);
    if (planLpOverlay && planLpOverlay.revisionId !== revId) return true;
    if (planSurfaceMap && planSurfaceMap.revisionId !== revId) return true;
    return false;
  },

  applySurfaceMapFromManifest: ({ jobId, revisionId, grid }) => {
    if (grid.nx < 1 || grid.ny < 1 || grid.lpDb.length < grid.nx * grid.ny) {
      set({ planSurfaceMap: null });
      return;
    }
    set({
      planSurfaceMap: {
        jobId,
        revisionId,
        zM: grid.zM ?? 1.5,
        originX: grid.originX,
        originY: grid.originY,
        cellSizeM: grid.cellSizeM,
        nx: grid.nx,
        ny: grid.ny,
        lpDb: [...grid.lpDb],
      },
    });
  },

  applyPunctualLpToWorkplaces: ({
    jobId,
    revisionId,
    fixtureReplay,
    punctual,
  }) => {
    const workplaces = get().model.workplaces;
    const byWorkplaceId: Record<string, number> = {};
    const safeName = (name: string) =>
      name.replace(/[^a-zA-Z0-9_-]/g, "_").slice(0, 40) || "wp";
    const used = new Set<number>();
    for (const wp of workplaces) {
      const idx = punctual.findIndex(
        (p, i) =>
          !used.has(i) &&
          (p.receiverId === wp.name ||
            p.receiverId === safeName(wp.name) ||
            p.receiverId === wp.id),
      );
      const pick = idx >= 0 ? idx : punctual.findIndex((_, i) => !used.has(i));
      if (pick < 0) continue;
      used.add(pick);
      const lp = punctual[pick]?.lpDbGlobal;
      if (typeof lp === "number" && Number.isFinite(lp)) {
        byWorkplaceId[wp.id] = lp;
      }
    }
    if (Object.keys(byWorkplaceId).length === 0) {
      set({ planLpOverlay: null });
      return;
    }
    set({
      planLpOverlay: {
        byWorkplaceId,
        jobId,
        revisionId,
        fixtureReplay,
      },
    });
  },
}));

function asOptionalUuid(value: string | null | undefined): Uuid | undefined {
  if (value && isUuid(value)) {
    return value;
  }
  return undefined;
}
