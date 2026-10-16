import { useMemo, useState } from "react";
import { Stage, Layer, Line, Circle, Text, Group } from "react-konva";
import type Konva from "konva";
import { stripClosingDuplicate } from "@sonoplan/domain";
import { contourToFlatPoints, contourBounds } from "../model/contourHelpers";
import { useEditorStore } from "../store/editorStore";

const STAGE_PAD = 24;

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
  width: number;
  height: number;
}

export function PlanCanvas({ width, height }: PlanCanvasProps) {
  const model = useEditorStore((s) => s.model);
  const selection = useEditorStore((s) => s.selection);
  const toolMode = useEditorStore((s) => s.toolMode);
  const polygonDraft = useEditorStore((s) => s.polygonDraft);
  const setSelection = useEditorStore((s) => s.setSelection);
  const addPolygonVertex = useEditorStore((s) => s.addPolygonVertex);
  const addSource = useEditorStore((s) => s.addSource);
  const addWorkplace = useEditorStore((s) => s.addWorkplace);
  const updateSourcePosition = useEditorStore((s) => s.updateSourcePosition);
  const updateWorkplacePosition = useEditorStore(
    (s) => s.updateWorkplacePosition,
  );

  const [placeMode, setPlaceMode] = useState<"none" | "source" | "workplace">(
    "none",
  );

  const room = model.rooms[0];
  const bounds = useMemo(() => {
    if (!room) {
      return { minX: 0, minY: 0, maxX: 20, maxY: 12, width: 20, depth: 12 };
    }
    return contourBounds(room.floorContour);
  }, [room]);

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

  const onStageClick = (e: Konva.KonvaEventObject<MouseEvent | TouchEvent>) => {
    const stage = e.target.getStage();
    if (!stage) return;
    const pos = stage.getPointerPosition();
    if (!pos) return;
    const p = stageToProject(pos.x, pos.y, transform);

    if (toolMode === "drawPolygon") {
      addPolygonVertex(p.x, p.y);
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
      <div className="plan-place-bar" role="toolbar" aria-label="Размещение">
        <button
          type="button"
          className={
            placeMode === "source" ? "btn btn--active" : "btn"
          }
          onClick={() =>
            setPlaceMode((m) => (m === "source" ? "none" : "source"))
          }
        >
          + Источник
        </button>
        <button
          type="button"
          className={
            placeMode === "workplace" ? "btn btn--active" : "btn"
          }
          onClick={() =>
            setPlaceMode((m) => (m === "workplace" ? "none" : "workplace"))
          }
        >
          + РМ
        </button>
        {placeMode !== "none" && (
          <span className="plan-place-hint">Каснитесь плана</span>
        )}
      </div>
      <Stage
        width={width}
        height={height}
        onClick={onStageClick}
        onTap={onStageClick}
        className="plan-stage"
      >
        <Layer>
          {roomPoints.length >= 6 && (
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
          {room &&
            stripClosingDuplicate(room.floorContour).map((v, i) => (
              <Circle
                key={`v-${i}`}
                x={transform.offsetX + v.x * transform.scale}
                y={transform.offsetY - v.y * transform.scale}
                radius={4}
                fill="#2c5f7c"
              />
            ))}
          {draftPoints.length >= 2 && (
            <Line
              points={draftPoints}
              stroke="#b45309"
              strokeWidth={2}
              dash={[6, 4]}
            />
          )}
          {polygonDraft.map((v, i) => (
            <Circle
              key={`d-${i}`}
              x={transform.offsetX + v.x * transform.scale}
              y={transform.offsetY - v.y * transform.scale}
              radius={5}
              fill="#b45309"
            />
          ))}
          {model.sources.map((src) => {
            const selected =
              selection?.kind === "source" && selection.id === src.id;
            const cx = transform.offsetX + src.position.x * transform.scale;
            const cy = transform.offsetY - src.position.y * transform.scale;
            return (
              <Group
                key={src.id}
                x={cx}
                y={cy}
                draggable={toolMode === "move" && selected}
                onClick={(e) => {
                  e.cancelBubble = true;
                  setSelection({ kind: "source", id: src.id });
                }}
                onTap={(e) => {
                  e.cancelBubble = true;
                  setSelection({ kind: "source", id: src.id });
                }}
                onDragEnd={(e) => {
                  const node = e.target;
                  const p = stageToProject(node.x(), node.y(), transform);
                  updateSourcePosition(p.x, p.y, src.position.z);
                }}
              >
                <Circle
                  radius={selected ? 14 : 12}
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
          {model.workplaces.map((wp) => {
            const selected =
              selection?.kind === "workplace" && selection.id === wp.id;
            const cx = transform.offsetX + wp.position.x * transform.scale;
            const cy = transform.offsetY - wp.position.y * transform.scale;
            return (
              <Group
                key={wp.id}
                x={cx}
                y={cy}
                draggable={toolMode === "move" && selected}
                onClick={(e) => {
                  e.cancelBubble = true;
                  setSelection({ kind: "workplace", id: wp.id });
                }}
                onTap={(e) => {
                  e.cancelBubble = true;
                  setSelection({ kind: "workplace", id: wp.id });
                }}
                onDragEnd={(e) => {
                  const node = e.target;
                  const p = stageToProject(node.x(), node.y(), transform);
                  updateWorkplacePosition(p.x, p.y, wp.position.z);
                  node.position({ x: cx, y: cy });
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
              </Group>
            );
          })}
        </Layer>
      </Stage>
    </div>
  );
}
