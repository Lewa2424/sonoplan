import { useEffect, useMemo, useRef, useState } from "react";
import { Stage, Layer, Line, Circle, Text, Group, Image as KonvaImage } from "react-konva";
import type Konva from "konva";
import {
  buildDiffuseFieldInput,
  estimateLpAt,
  estimateLpGrid,
  stripClosingDuplicate,
  type ModelSnapshot,
} from "@sonoplan/domain";
import { useElementSize } from "../hooks/useElementSize";
import { ru } from "../i18n/ru";
import {
  contourAngleLabelPositions,
  contourBounds,
  contourToFlatPoints,
  contourVertexAngles,
  formatAngleDeg,
  formatAngleDegInt,
  openPolylineCornerAngleDeg,
  POLYGON_CLOSE_SNAP_M,
} from "../model/contourHelpers";
import {
  computeLpScale,
  formatLpScaleLegend,
  surfaceMapToCanvas,
  surfaceMapToDataUrl,
} from "../model/lpPalette";
import { useEditorStore } from "../store/editorStore";

const STAGE_PAD = 24;
const VERTEX_HIT_R = 12;
const POLYGON_CLOSE_SNAP_PX = 18;

interface ViewTransform {
  scale: number;
  offsetX: number;
  offsetY: number;
}

function computeTransform(
  width: number,
  height: number,
  modelBounds: { minX: number; minY: number; width: number; depth: number },
): ViewTransform {
  const worldW = Math.max(modelBounds.width, 1);
  const worldD = Math.max(modelBounds.depth, 1);
  const availW = Math.max(width - STAGE_PAD * 2, 40);
  const availH = Math.max(height - STAGE_PAD * 2, 40);
  const scale = Math.min(availW / worldW, availH / worldD);
  const offsetX = STAGE_PAD - modelBounds.minX * scale;
  const offsetY = height - STAGE_PAD + modelBounds.minY * scale;
  return { scale, offsetX, offsetY };
}

function stageToProject(
  sx: number,
  sy: number,
  t: ViewTransform,
): { x: number; y: number } {
  return {
    x: (sx - t.offsetX) / t.scale,
    y: (t.offsetY - sy) / t.scale,
  };
}

interface PlanCanvasProps {
  width?: number;
  height?: number;
}

/** Live position while a source / workplace is being dragged (not yet in store). */
interface DragOverride {
  readonly kind: "source" | "workplace";
  readonly id: string;
  readonly x: number;
  readonly y: number;
}

const DEFAULT_ESTIMATE_Z_M = 1.5;

function withDragOverride(
  model: ModelSnapshot,
  drag: DragOverride | null,
): ModelSnapshot {
  if (!drag) return model;
  if (drag.kind === "source") {
    return {
      ...model,
      sources: model.sources.map((s) =>
        s.id === drag.id
          ? { ...s, position: { ...s.position, x: drag.x, y: drag.y } }
          : s,
      ),
    };
  }
  return {
    ...model,
    workplaces: model.workplaces.map((w) =>
      w.id === drag.id
        ? { ...w, position: { ...w.position, x: drag.x, y: drag.y } }
        : w,
    ),
  };
}

function receiverZ(w: ModelSnapshot["workplaces"][number]): number {
  const h = w.receiverHeightM.value;
  if (h !== null && Number.isFinite(h) && h > 0) return h;
  return w.position.z > 0.05 ? w.position.z : DEFAULT_ESTIMATE_Z_M;
}

export function PlanCanvas(_props: PlanCanvasProps) {
  const stageHostRef = useRef<HTMLDivElement>(null);
  const { width, height } = useElementSize(stageHostRef);

  const model = useEditorStore((s) => s.model);
  const selection = useEditorStore((s) => s.selection);
  const toolMode = useEditorStore((s) => s.toolMode);
  const setToolMode = useEditorStore((s) => s.setToolMode);
  const polygonDraft = useEditorStore((s) => s.polygonDraft);
  const setSelection = useEditorStore((s) => s.setSelection);
  const addPolygonVertex = useEditorStore((s) => s.addPolygonVertex);
  const finishPolygon = useEditorStore((s) => s.finishPolygon);
  const updatePolygonDraftVertex = useEditorStore(
    (s) => s.updatePolygonDraftVertex,
  );
  const updateRoomVertex = useEditorStore((s) => s.updateRoomVertex);
  const addSource = useEditorStore((s) => s.addSource);
  const addWorkplace = useEditorStore((s) => s.addWorkplace);
  const addEquipmentAt = useEditorStore((s) => s.addEquipmentAt);
  const addSolidAt = useEditorStore((s) => s.addSolidAt);
  const pendingEquipmentKey = useEditorStore((s) => s.pendingEquipmentKey);
  const pendingSolidKind = useEditorStore((s) => s.pendingSolidKind);
  const updateSourcePosition = useEditorStore((s) => s.updateSourcePosition);
  const updateWorkplacePosition = useEditorStore(
    (s) => s.updateWorkplacePosition,
  );
  const moveSelectedBy = useEditorStore((s) => s.moveSelectedBy);
  const planLpOverlay = useEditorStore((s) => s.planLpOverlay);
  const planSurfaceMap = useEditorStore((s) => s.planSurfaceMap);
  const isPlanResultStale = useEditorStore((s) => s.isPlanResultStale);

  const [placeMode, setPlaceMode] = useState<"none" | "source" | "workplace">(
    "none",
  );
  const [heatmapImg, setHeatmapImg] = useState<HTMLImageElement | null>(null);
  const [dragOverride, setDragOverride] = useState<DragOverride | null>(null);
  const [preferEstimate, setPreferEstimate] = useState(false);
  /** Absolute angle labels (inside perimeter) — neighbors only while dragging. */
  const roomLabelRefs = useRef<(Konva.Text | null)[]>([]);
  const draftLabelRefs = useRef<(Konva.Text | null)[]>([]);

  const beginRoomVertexDrag = (dragIndex: number) => {
    const label = roomLabelRefs.current[dragIndex];
    if (label) {
      label.visible(false);
      label.getLayer()?.batchDraw();
    }
  };

  const updateNeighborRoomAngles = (
    pts: { x: number; y: number }[],
    dragIndex: number,
  ) => {
    const n = pts.length;
    if (n < 3) return;
    const angles = contourVertexAngles(pts);
    const positions = contourAngleLabelPositions(
      pts,
      transform.scale,
      transform.offsetX,
      transform.offsetY,
    );
    const neighbors = [(dragIndex - 1 + n) % n, (dragIndex + 1) % n].filter(
      (ni, idx, arr) => arr.indexOf(ni) === idx && ni !== dragIndex,
    );

    for (let i = 0; i < n; i++) {
      const label = roomLabelRefs.current[i];
      if (!label) continue;
      if (i === dragIndex) {
        label.visible(false);
        continue;
      }
      const ang = angles[i];
      const pos = positions[i];
      if (!ang || !pos) continue;
      const isNeighbor = neighbors.includes(i);
      label.visible(true);
      label.position({ x: pos.x, y: pos.y });
      label.offsetX(0);
      label.offsetY(0);
      if (isNeighbor) {
        label.text(formatAngleDegInt(ang.degrees));
        label.fontSize(15);
        label.fill("#b45309");
      } else {
        label.text(formatAngleDeg(ang.degrees));
        label.fontSize(11);
        label.fill(ang.nearRightAngle ? "#b45309" : "#1a2332");
      }
    }
    roomLabelRefs.current[0]?.getLayer()?.batchDraw();
  };

  const updateNeighborDraftAngles = (
    pts: { x: number; y: number }[],
    dragIndex: number,
  ) => {
    const candidates = [dragIndex - 1, dragIndex + 1].filter(
      (ni) => ni > 0 && ni < pts.length - 1 && ni !== dragIndex,
    );
    if (dragIndex === pts.length - 1 && pts.length >= 3) {
      candidates.push(pts.length - 2);
    }
    if (dragIndex === 0 && pts.length >= 3) {
      candidates.push(1);
    }
    const uniq = [...new Set(candidates)];
    const positions = contourAngleLabelPositions(
      pts,
      transform.scale,
      transform.offsetX,
      transform.offsetY,
    );
    for (let i = 0; i < pts.length; i++) {
      const label = draftLabelRefs.current[i];
      if (!label) continue;
      if (i === dragIndex) {
        label.visible(false);
        continue;
      }
      const live = openPolylineCornerAngleDeg(pts, i);
      const pos = positions[i];
      if (live === null || !pos) {
        label.visible(false);
        continue;
      }
      label.visible(true);
      label.position({ x: pos.x, y: pos.y });
      if (uniq.includes(i)) {
        label.text(formatAngleDegInt(live));
        label.fontSize(15);
        label.fill("#b45309");
      } else {
        label.text(formatAngleDeg(live));
        label.fontSize(11);
        label.fill("#1a2332");
      }
    }
    draftLabelRefs.current[1]?.getLayer()?.batchDraw();
  };

  const room = model.rooms[0];
  const placingCatalog =
    pendingEquipmentKey !== null || pendingSolidKind !== null;
  const passClicksToStage =
    toolMode === "drawPolygon" || placeMode !== "none" || placingCatalog;
  const stale = isPlanResultStale();

  const mapScale = useMemo(() => {
    if (!planSurfaceMap || stale) return null;
    return computeLpScale(planSurfaceMap.lpDb);
  }, [planSurfaceMap, stale]);

  const heatmapUrl = useMemo(() => {
    if (!planSurfaceMap || stale || !mapScale) return null;
    return surfaceMapToDataUrl({
      nx: planSurfaceMap.nx,
      ny: planSurfaceMap.ny,
      lpDb: planSurfaceMap.lpDb,
      scale: mapScale,
    });
  }, [planSurfaceMap, stale, mapScale]);

  useEffect(() => {
    if (!heatmapUrl) {
      setHeatmapImg(null);
      return;
    }
    const img = new window.Image();
    img.onload = () => setHeatmapImg(img);
    img.src = heatmapUrl;
  }, [heatmapUrl]);

  // A fresh SPPS map should be what the user sees first.
  const sppsJobId = planSurfaceMap?.jobId ?? null;
  useEffect(() => {
    if (sppsJobId) setPreferEstimate(false);
  }, [sppsJobId]);

  const sppsMapFresh = Boolean(heatmapImg && planSurfaceMap && mapScale && !stale);
  const showSppsMap = sppsMapFresh && !preferEstimate && !dragOverride;

  const estimateModel = useMemo(
    () => withDragOverride(model, dragOverride),
    [model, dragOverride],
  );
  const estimateInput = useMemo(
    () => buildDiffuseFieldInput(estimateModel),
    [estimateModel],
  );
  const estimateZ = useMemo(() => {
    const zs = estimateModel.workplaces.map(receiverZ);
    return zs.length > 0
      ? zs.reduce((a, b) => a + b, 0) / zs.length
      : DEFAULT_ESTIMATE_Z_M;
  }, [estimateModel.workplaces]);
  const estimateGrid = useMemo(
    () =>
      estimateInput.ok && !showSppsMap
        ? estimateLpGrid(estimateInput.input, estimateZ)
        : null,
    [estimateInput, estimateZ, showSppsMap],
  );
  const estimateScale = useMemo(
    () => (estimateGrid ? computeLpScale(estimateGrid.lpDb) : null),
    [estimateGrid],
  );
  const estimateCanvas = useMemo(
    () =>
      estimateGrid && estimateScale
        ? surfaceMapToCanvas({
            nx: estimateGrid.nx,
            ny: estimateGrid.ny,
            lpDb: estimateGrid.lpDb,
            scale: estimateScale,
          })
        : null,
    [estimateGrid, estimateScale],
  );
  const estimateByWorkplaceId = useMemo(() => {
    const out = new Map<string, number>();
    if (!estimateInput.ok) return out;
    for (const w of estimateModel.workplaces) {
      const lp = estimateLpAt(
        estimateInput.input,
        w.position.x,
        w.position.y,
        receiverZ(w),
      );
      if (lp !== null) out.set(w.id, lp);
    }
    return out;
  }, [estimateInput, estimateModel.workplaces]);

  const bounds = useMemo(() => {
    if (!room) {
      return { minX: 0, minY: 0, maxX: 20, maxY: 12, width: 20, depth: 12 };
    }
    const roomB = contourBounds(room.floorContour);
    if (polygonDraft.length === 0) return roomB;
    const draftB = contourBounds(polygonDraft);
    const minX = Math.min(roomB.minX, draftB.minX);
    const minY = Math.min(roomB.minY, draftB.minY);
    const maxX = Math.max(roomB.maxX, draftB.maxX);
    const maxY = Math.max(roomB.maxY, draftB.maxY);
    return {
      minX,
      minY,
      maxX,
      maxY,
      width: Math.max(maxX - minX, 1),
      depth: Math.max(maxY - minY, 1),
    };
  }, [room, polygonDraft]);

  const transform = useMemo(
    () => computeTransform(width, height, bounds),
    [width, height, bounds],
  );

  const roomPoints = useMemo(() => {
    if (!room) return [];
    return contourToFlatPoints(
      room.floorContour,
      transform.scale,
      transform.offsetX,
      transform.offsetY,
    );
  }, [room, transform]);

  const draftPoints = useMemo(
    () =>
      contourToFlatPoints(
        polygonDraft,
        transform.scale,
        transform.offsetX,
        transform.offsetY,
      ),
    [polygonDraft, transform],
  );

  const roomAngles = useMemo(
    () => (room ? contourVertexAngles(room.floorContour) : []),
    [room],
  );

  const roomUnique = useMemo(
    () => (room ? stripClosingDuplicate(room.floorContour) : []),
    [room],
  );

  const roomLabelPositions = useMemo(
    () =>
      room
        ? contourAngleLabelPositions(
            room.floorContour,
            transform.scale,
            transform.offsetX,
            transform.offsetY,
          )
        : [],
    [room, transform],
  );

  const draftLabelPositions = useMemo(
    () =>
      polygonDraft.length >= 3
        ? contourAngleLabelPositions(
            polygonDraft,
            transform.scale,
            transform.offsetX,
            transform.offsetY,
          )
        : [],
    [polygonDraft, transform],
  );

  const onStageClick = (e: Konva.KonvaEventObject<MouseEvent | TouchEvent>) => {
    const stage = e.target.getStage();
    if (!stage) return;
    const pos = stage.getPointerPosition();
    if (!pos) return;
    const p = stageToProject(pos.x, pos.y, transform);

    if (toolMode === "drawPolygon") {
      // Clicks on empty stage add a vertex; dragging existing draft handles move.
      if (e.target !== stage && e.target.getClassName() !== "Layer") {
        return;
      }
      const first = polygonDraft[0];
      if (first && polygonDraft.length >= 3) {
        const distM = Math.hypot(p.x - first.x, p.y - first.y);
        const distPx = distM * transform.scale;
        if (distM <= POLYGON_CLOSE_SNAP_M || distPx <= POLYGON_CLOSE_SNAP_PX) {
          finishPolygon();
          return;
        }
      }
      addPolygonVertex(p.x, p.y);
      return;
    }
    if (pendingEquipmentKey) {
      addEquipmentAt(p.x, p.y, pendingEquipmentKey);
      return;
    }
    if (pendingSolidKind) {
      addSolidAt(p.x, p.y, pendingSolidKind);
      return;
    }
    if (placeMode === "source") {
      addSource(p.x, p.y);
      setPlaceMode("none");
      return;
    }
    if (placeMode === "workplace") {
      addWorkplace(p.x, p.y);
      setPlaceMode("none");
      return;
    }
    if (e.target === stage) {
      setSelection(null);
    }
  };

  return (
    <div className="plan-wrap">
      <div className="plan-place-bar" role="toolbar" aria-label="Режим и размещение">
        <button
          type="button"
          className={toolMode === "select" ? "btn btn--active" : "btn"}
          onClick={() => {
            setToolMode("select");
            setPlaceMode("none");
          }}
        >
          Выбор
        </button>
        <button
          type="button"
          className={toolMode === "move" ? "btn btn--active" : "btn"}
          onClick={() => {
            setToolMode("move");
            setPlaceMode("none");
          }}
          title="Тяните источник или РМ по плану"
        >
          Переместить
        </button>
        <span className="plan-place-sep" aria-hidden="true" />
        <button
          type="button"
          className={placeMode === "source" ? "btn btn--active" : "btn"}
          onClick={() => {
            setToolMode("select");
            setPlaceMode((m) => (m === "source" ? "none" : "source"));
          }}
        >
          + Источник
        </button>
        <button
          type="button"
          className={placeMode === "workplace" ? "btn btn--active" : "btn"}
          onClick={() => {
            setToolMode("select");
            setPlaceMode((m) => (m === "workplace" ? "none" : "workplace"));
          }}
        >
          + РМ
        </button>
        {(placeMode !== "none" ||
          toolMode === "drawPolygon" ||
          toolMode === "move" ||
          placingCatalog) && (
          <span className="plan-place-hint">
            {toolMode === "drawPolygon"
              ? "Каснитесь — вершина; у 1-й точки — замыкание; тяните — углы соседей"
              : toolMode === "move"
                ? "Тяните объект пальцем"
                : placingCatalog
                  ? "Каснитесь плана — разместить"
                  : "Каснитесь плана"}
          </span>
        )}
      </div>
      {stale && (planLpOverlay || planSurfaceMap) ? (
        <p className="banner banner--warn">{ru.model.staleLp}</p>
      ) : null}
      {showSppsMap && mapScale ? (
        <p className="page-meta plan-map-scale" aria-live="polite">
          {ru.calculations.mapScaleOnPlan}: {formatLpScaleLegend(mapScale)}
        </p>
      ) : estimateCanvas && estimateScale ? (
        <>
          <p className="page-meta plan-map-scale" aria-live="polite">
            {ru.model.estimateLegend}, {ru.model.estimateAtHeight}{" "}
            {estimateZ.toFixed(1)} м: {formatLpScaleLegend(estimateScale)}
          </p>
          <p className="page-hint plan-estimate-note">{ru.model.estimateNote}</p>
        </>
      ) : !estimateInput.ok && !showSppsMap ? (
        <p className="page-hint plan-estimate-note">
          {ru.model.estimateUnavailable[estimateInput.reason]}
        </p>
      ) : null}
      {sppsMapFresh ? (
        <p className="plan-map-toggle">
          <button
            type="button"
            className="btn"
            onClick={() => setPreferEstimate((v) => !v)}
          >
            {preferEstimate ? ru.model.showSppsMap : ru.model.showEstimateMap}
          </button>
        </p>
      ) : null}
      <div className="plan-stage-host" ref={stageHostRef}>
      <Stage
        width={width}
        height={height}
        onClick={onStageClick}
        onTap={onStageClick}
        className="plan-stage"
      >
        <Layer>
          {toolMode !== "drawPolygon" && roomPoints.length >= 6 && (
            <Line
              points={roomPoints}
              closed
              fill="#dce8ef"
              stroke={
                selection?.kind === "room" && selection.id === room?.id
                  ? "#2c5f7c"
                  : "#5a6575"
              }
              strokeWidth={selection?.kind === "room" ? 3 : 2}
              listening={!passClicksToStage}
              onClick={(e) => {
                e.cancelBubble = true;
                if (room) setSelection({ kind: "room", id: room.id });
              }}
              onTap={(e) => {
                e.cancelBubble = true;
                if (room) setSelection({ kind: "room", id: room.id });
              }}
            />
          )}
          {!showSppsMap && estimateCanvas && estimateGrid ? (
            <KonvaImage
              image={estimateCanvas}
              x={transform.offsetX + estimateGrid.originX * transform.scale}
              y={
                transform.offsetY -
                (estimateGrid.originY + estimateGrid.ny * estimateGrid.cellSizeM) *
                  transform.scale
              }
              width={estimateGrid.nx * estimateGrid.cellSizeM * transform.scale}
              height={estimateGrid.ny * estimateGrid.cellSizeM * transform.scale}
              listening={false}
              opacity={0.75}
            />
          ) : null}
          {showSppsMap && heatmapImg && planSurfaceMap ? (
            <KonvaImage
              image={heatmapImg}
              x={
                transform.offsetX + planSurfaceMap.originX * transform.scale
              }
              y={
                transform.offsetY -
                (planSurfaceMap.originY +
                  planSurfaceMap.ny * planSurfaceMap.cellSizeYM) *
                  transform.scale
              }
              width={planSurfaceMap.nx * planSurfaceMap.cellSizeM * transform.scale}
              height={
                planSurfaceMap.ny * planSurfaceMap.cellSizeYM * transform.scale
              }
              listening={false}
              opacity={0.85}
            />
          ) : null}
          {toolMode !== "drawPolygon" &&
            model.solids.map((solid) => {
              const pts = contourToFlatPoints(
                solid.floorContour,
                transform.scale,
                transform.offsetX,
                transform.offsetY,
              );
              const selected =
                selection?.kind === "solid" && selection.id === solid.id;
              return (
                <Line
                  key={solid.id}
                  points={pts}
                  closed
                  fill={selected ? "rgba(90, 101, 117, 0.45)" : "rgba(90, 101, 117, 0.28)"}
                  stroke={selected ? "#1a2332" : "#5a6575"}
                  strokeWidth={selected ? 2 : 1}
                  listening={!passClicksToStage}
                  onClick={(e) => {
                    e.cancelBubble = true;
                    setSelection({ kind: "solid", id: solid.id });
                  }}
                  onTap={(e) => {
                    e.cancelBubble = true;
                    setSelection({ kind: "solid", id: solid.id });
                  }}
                  draggable={toolMode === "move" && !passClicksToStage}
                  onDragEnd={(e) => {
                    e.cancelBubble = true;
                    const node = e.target;
                    const dx = node.x() / transform.scale;
                    const dy = -node.y() / transform.scale;
                    node.position({ x: 0, y: 0 });
                    setSelection({ kind: "solid", id: solid.id });
                    moveSelectedBy(dx, dy);
                  }}
                />
              );
            })}
          {toolMode !== "drawPolygon" &&
            roomUnique.map((v, i) => {
              const sx = transform.offsetX + v.x * transform.scale;
              const sy = transform.offsetY - v.y * transform.scale;
              return (
                <Group
                  key={`v-${i}`}
                  x={sx}
                  y={sy}
                  // Contour vertices: edit in «Выбор», not in «Переместить».
                  draggable={toolMode === "select" && !passClicksToStage}
                  onMouseDown={(e) => {
                    e.cancelBubble = true;
                  }}
                  onTouchStart={(e) => {
                    e.cancelBubble = true;
                  }}
                  onDragStart={(e) => {
                    e.cancelBubble = true;
                    beginRoomVertexDrag(i);
                  }}
                  onDragMove={(e) => {
                    e.cancelBubble = true;
                    const node = e.target;
                    const p = stageToProject(node.x(), node.y(), transform);
                    const pts = roomUnique.map((pt, idx) =>
                      idx === i ? p : pt,
                    );
                    updateNeighborRoomAngles(pts, i);
                  }}
                  onDragEnd={(e) => {
                    e.cancelBubble = true;
                    const node = e.target;
                    const p = stageToProject(node.x(), node.y(), transform);
                    updateRoomVertex(i, p.x, p.y);
                    if (room) setSelection({ kind: "room", id: room.id });
                  }}
                  onClick={(e) => {
                    e.cancelBubble = true;
                    if (room) setSelection({ kind: "room", id: room.id });
                  }}
                  onTap={(e) => {
                    e.cancelBubble = true;
                    if (room) setSelection({ kind: "room", id: room.id });
                  }}
                >
                  <Circle
                    radius={VERTEX_HIT_R}
                    fill="transparent"
                    strokeEnabled={false}
                  />
                  <Circle radius={5} fill="#2c5f7c" listening={false} />
                </Group>
              );
            })}
          {toolMode !== "drawPolygon" &&
            roomAngles.map((ang, i) => {
              const pos = roomLabelPositions[i];
              if (!pos) return null;
              return (
                <Text
                  key={`ang-${i}`}
                  ref={(node) => {
                    roomLabelRefs.current[i] = node;
                  }}
                  x={pos.x}
                  y={pos.y}
                  text={formatAngleDeg(ang.degrees)}
                  fontSize={11}
                  fill={ang.nearRightAngle ? "#b45309" : "#1a2332"}
                  offsetX={12}
                  offsetY={6}
                  listening={false}
                />
              );
            })}
          {draftPoints.length >= 2 && (
            <Line
              points={draftPoints}
              stroke="#b45309"
              strokeWidth={2}
              dash={[6, 4]}
              listening={false}
            />
          )}
          {polygonDraft.map((v, i) => {
            const sx = transform.offsetX + v.x * transform.scale;
            const sy = transform.offsetY - v.y * transform.scale;
            const isCloseTarget =
              i === 0 && polygonDraft.length >= 3 && toolMode === "drawPolygon";
            return (
              <Group
                key={`d-${i}`}
                x={sx}
                y={sy}
                draggable={toolMode === "drawPolygon"}
                onMouseDown={(e) => {
                  e.cancelBubble = true;
                }}
                onTouchStart={(e) => {
                  e.cancelBubble = true;
                }}
                onDragStart={(e) => {
                  e.cancelBubble = true;
                  draftLabelRefs.current[i]?.visible(false);
                }}
                onDragMove={(e) => {
                  e.cancelBubble = true;
                  const node = e.target;
                  const p = stageToProject(node.x(), node.y(), transform);
                  const pts = polygonDraft.map((pt, idx) =>
                    idx === i ? p : pt,
                  );
                  updateNeighborDraftAngles(pts, i);
                }}
                onDragEnd={(e) => {
                  e.cancelBubble = true;
                  const node = e.target;
                  const p = stageToProject(node.x(), node.y(), transform);
                  updatePolygonDraftVertex(i, p.x, p.y);
                }}
                onClick={(e) => {
                  if (!isCloseTarget) return;
                  e.cancelBubble = true;
                  finishPolygon();
                }}
                onTap={(e) => {
                  if (!isCloseTarget) return;
                  e.cancelBubble = true;
                  finishPolygon();
                }}
              >
                {isCloseTarget ? (
                  <Circle
                    radius={Math.max(VERTEX_HIT_R, POLYGON_CLOSE_SNAP_PX)}
                    stroke="#b45309"
                    strokeWidth={2}
                    dash={[4, 3]}
                    fill="rgba(180, 83, 9, 0.12)"
                  />
                ) : (
                  <Circle
                    radius={VERTEX_HIT_R}
                    fill="transparent"
                    strokeEnabled={false}
                  />
                )}
                <Circle radius={6} fill="#b45309" listening={false} />
              </Group>
            );
          })}
          {polygonDraft.length >= 3 &&
            polygonDraft.map((_, i) => {
              if (i <= 0 || i >= polygonDraft.length - 1) return null;
              const live = openPolylineCornerAngleDeg(polygonDraft, i);
              const pos = draftLabelPositions[i];
              if (live === null || !pos) return null;
              return (
                <Text
                  key={`dang-${i}`}
                  ref={(node) => {
                    draftLabelRefs.current[i] = node;
                  }}
                  x={pos.x}
                  y={pos.y}
                  text={formatAngleDeg(live)}
                  fontSize={11}
                  fill="#1a2332"
                  offsetX={12}
                  offsetY={6}
                  listening={false}
                />
              );
            })}
          {toolMode !== "drawPolygon" &&
            model.sources.map((src) => {
              const selected =
                selection?.kind === "source" && selection.id === src.id;
              const cx = transform.offsetX + src.position.x * transform.scale;
              const cy = transform.offsetY - src.position.y * transform.scale;
              return (
                <Group
                  key={src.id}
                  x={cx}
                  y={cy}
                  listening={!passClicksToStage}
                  draggable={toolMode === "move" && !passClicksToStage}
                  onClick={(e) => {
                    e.cancelBubble = true;
                    setSelection({ kind: "source", id: src.id });
                  }}
                  onTap={(e) => {
                    e.cancelBubble = true;
                    setSelection({ kind: "source", id: src.id });
                  }}
                  onDragStart={(e) => {
                    e.cancelBubble = true;
                    setSelection({ kind: "source", id: src.id });
                  }}
                  onDragMove={(e) => {
                    e.cancelBubble = true;
                    const p = stageToProject(e.target.x(), e.target.y(), transform);
                    setDragOverride({ kind: "source", id: src.id, x: p.x, y: p.y });
                  }}
                  onDragEnd={(e) => {
                    e.cancelBubble = true;
                    const node = e.target;
                    const p = stageToProject(node.x(), node.y(), transform);
                    updateSourcePosition(p.x, p.y, src.position.z);
                    setDragOverride(null);
                  }}
                >
                  <Circle
                    radius={selected || toolMode === "move" ? 14 : 12}
                    fill="#c45c26"
                    stroke="#1a2332"
                    strokeWidth={selected ? 2 : 1}
                  />
                  <Text
                    text="Lw"
                    fontSize={10}
                    fill="#fff"
                    offsetX={7}
                    offsetY={4}
                  />
                </Group>
              );
            })}
          {toolMode !== "drawPolygon" &&
            model.workplaces.map((wp) => {
              const selected =
                selection?.kind === "workplace" && selection.id === wp.id;
              const cx = transform.offsetX + wp.position.x * transform.scale;
              const cy = transform.offsetY - wp.position.y * transform.scale;
              const lp = stale
                ? undefined
                : planLpOverlay?.byWorkplaceId[wp.id];
              const draggingThis =
                dragOverride !== null &&
                (dragOverride.kind === "source" || dragOverride.id === wp.id);
              const lpLabel =
                !draggingThis && typeof lp === "number" && Number.isFinite(lp)
                  ? `${lp.toFixed(1)} дБ`
                  : null;
              const est = estimateByWorkplaceId.get(wp.id);
              const estLabel =
                lpLabel === null && est !== undefined
                  ? `${ru.model.estimatePrefix}${est.toFixed(1)} дБ`
                  : null;
              return (
                <Group
                  key={wp.id}
                  x={cx}
                  y={cy}
                  listening={!passClicksToStage}
                  draggable={toolMode === "move" && !passClicksToStage}
                  onClick={(e) => {
                    e.cancelBubble = true;
                    setSelection({ kind: "workplace", id: wp.id });
                  }}
                  onTap={(e) => {
                    e.cancelBubble = true;
                    setSelection({ kind: "workplace", id: wp.id });
                  }}
                  onDragStart={(e) => {
                    e.cancelBubble = true;
                    setSelection({ kind: "workplace", id: wp.id });
                  }}
                  onDragMove={(e) => {
                    e.cancelBubble = true;
                    const p = stageToProject(e.target.x(), e.target.y(), transform);
                    setDragOverride({ kind: "workplace", id: wp.id, x: p.x, y: p.y });
                  }}
                  onDragEnd={(e) => {
                    e.cancelBubble = true;
                    const node = e.target;
                    const p = stageToProject(node.x(), node.y(), transform);
                    updateWorkplacePosition(p.x, p.y, wp.position.z);
                    setDragOverride(null);
                  }}
                >
                  <Circle
                    radius={selected ? 14 : 12}
                    fill="#2f6f4e"
                    stroke="#1a2332"
                    strokeWidth={selected ? 2 : 1}
                  />
                  <Text
                    text="РМ"
                    fontSize={9}
                    fill="#fff"
                    offsetX={8}
                    offsetY={4}
                  />
                  {lpLabel ? (
                    <Text
                      text={lpLabel}
                      fontSize={10}
                      fill="#0b3d2c"
                      fontStyle="bold"
                      x={-22}
                      y={16}
                    />
                  ) : estLabel ? (
                    <Text
                      text={estLabel}
                      fontSize={10}
                      fill="#4a5565"
                      fontStyle="italic"
                      x={-24}
                      y={16}
                    />
                  ) : null}
                </Group>
              );
            })}
        </Layer>
      </Stage>
      </div>
    </div>
  );
}
