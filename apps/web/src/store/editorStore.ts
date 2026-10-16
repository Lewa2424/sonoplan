import {
  isUuid,
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
import {
  createDefaultWorkshopRoom,
  createOfflineDraft,
  createSourceAt,
  createWorkplaceAt,
  parseDraftBody,
} from "../model/factoryModel";
import {
  ensureClosedContour,
  lShapeContour,
  rectangleContour,
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
  | null;

interface LastRevisionInfo {
  revisionId: string;
  snapshotHash: string;
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
  beginPolygon: () => void;
  addPolygonVertex: (x: number, y: number) => void;
  finishPolygon: () => void;
  cancelPolygon: () => void;
  addSource: (x: number, y: number) => void;
  addWorkplace: (x: number, y: number) => void;
  updateSelectedName: (name: string) => void;
  updateSourceLw: (levelDb: number) => void;
  updateSourcePosition: (x: number, y: number, z: number) => void;
  updateWorkplacePosition: (x: number, y: number, z: number) => void;
  moveSelectedBy: (dx: number, dy: number) => void;
  runValidate: () => Promise<void>;
  commitRevision: () => Promise<void>;
  saveDraft: () => Promise<void>;
  reloadDraft: () => Promise<void>;
  markDirty: () => void;
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

  beginPolygon: () =>
    set({ toolMode: "drawPolygon", polygonDraft: [], selection: null }),

  addPolygonVertex: (x, y) =>
    set((s) => ({ polygonDraft: [...s.polygonDraft, { x, y }] })),

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
      const contour = ensureClosedContour(polygonDraft);
      const next = withRoom(model, contour, roomHeightM);
      set({
        model: next,
        toolMode: "select",
        polygonDraft: [],
        selection: next.rooms[0]
          ? { kind: "room", id: next.rooms[0].id }
          : null,
        syncMessage: null,
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
        syncMessage: `Ревизия ${rev.revisionId.slice(0, 8)}… snapshotHash=${rev.snapshotHash.slice(0, 12)}…`,
      });
    } catch (err) {
      set({
        syncStatus: "error",
        syncMessage:
          err instanceof Error ? err.message : "Не удалось создать ревизию",
      });
    }
  },
}));

function asOptionalUuid(value: string | null | undefined): Uuid | undefined {
  if (value && isUuid(value)) {
    return value;
  }
  return undefined;
}
