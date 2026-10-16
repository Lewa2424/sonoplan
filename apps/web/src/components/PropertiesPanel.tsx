import {
  contourVertexAngles,
  formatAngleDeg,
} from "../model/contourHelpers";
import { useEditorStore } from "../store/editorStore";
import { STANDARD_BANDS_HZ } from "../model/factoryModel";

export function PropertiesPanel() {
  const selection = useEditorStore((s) => s.selection);
  const model = useEditorStore((s) => s.model);
  const roomHeightM = useEditorStore((s) => s.roomHeightM);
  const setRoomDimensions = useEditorStore((s) => s.setRoomDimensions);
  const roomWidthM = useEditorStore((s) => s.roomWidthM);
  const roomDepthM = useEditorStore((s) => s.roomDepthM);
  const applyRectangleRoom = useEditorStore((s) => s.applyRectangleRoom);
  const snapRoomRightAngles = useEditorStore((s) => s.snapRoomRightAngles);
  const updateSelectedName = useEditorStore((s) => s.updateSelectedName);
  const updateSourceLw = useEditorStore((s) => s.updateSourceLw);
  const updateSourcePosition = useEditorStore((s) => s.updateSourcePosition);
  const updateWorkplacePosition = useEditorStore(
    (s) => s.updateWorkplacePosition,
  );
  const markDirty = useEditorStore((s) => s.markDirty);

  if (!selection) {
    return (
      <aside className="props-panel" aria-label="Свойства">
        <p className="props-empty">Выберите объект на плане</p>
      </aside>
    );
  }

  if (selection.kind === "room") {
    const room = model.rooms.find((r) => r.id === selection.id);
    const angles = room ? contourVertexAngles(room.floorContour) : [];
    return (
      <aside className="props-panel" aria-label="Свойства помещения">
        <h3 className="props-title">Помещение</h3>
        <label className="field">
          <span>Ширина X, м</span>
          <input
            type="number"
            min={1}
            step={0.1}
            value={roomWidthM}
            onChange={(e) =>
              setRoomDimensions(
                Number(e.target.value),
                roomDepthM,
                roomHeightM,
              )
            }
          />
        </label>
        <label className="field">
          <span>Глубина Y, м</span>
          <input
            type="number"
            min={1}
            step={0.1}
            value={roomDepthM}
            onChange={(e) =>
              setRoomDimensions(
                roomWidthM,
                Number(e.target.value),
                roomHeightM,
              )
            }
          />
        </label>
        <label className="field">
          <span>Высота Z, м</span>
          <input
            type="number"
            min={0.5}
            step={0.1}
            value={room?.heightM.value ?? roomHeightM}
            onChange={(e) => {
              const h = Number(e.target.value);
              setRoomDimensions(roomWidthM, roomDepthM, h);
              useEditorStore.setState((s) => ({
                model: {
                  ...s.model,
                  rooms: s.model.rooms.map((r) =>
                    r.id === selection.id
                      ? { ...r, heightM: { value: h, unit: "m" } }
                      : r,
                  ),
                },
              }));
              markDirty();
            }}
          />
        </label>
        <button type="button" className="btn" onClick={applyRectangleRoom}>
          Применить прямоугольник
        </button>
        <button type="button" className="btn" onClick={snapRoomRightAngles}>
          Выровнять 90±5°
        </button>
        <p className="props-meta">
          Вершин контура: {room?.floorContour.length ?? 0} (замкнутый)
        </p>
        {angles.length > 0 ? (
          <ul className="props-angles" aria-label="Углы контура">
            {angles.map((a) => (
              <li key={a.index}>
                ∠{a.index + 1}: {formatAngleDeg(a.degrees)}
                {a.nearRightAngle ? " ≈90°" : ""}
              </li>
            ))}
          </ul>
        ) : null}
      </aside>
    );
  }

  if (selection.kind === "source") {
    const src = model.sources.find((s) => s.id === selection.id);
    if (!src) return null;
    const lw0 = src.powerSpectrumLw[0]?.level.value ?? 90;
    return (
      <aside className="props-panel" aria-label="Свойства источника">
        <h3 className="props-title">Источник</h3>
        <p className="props-badge">quantity: sound_power (Lw), дБ re 1 pW</p>
        <label className="field">
          <span>Имя</span>
          <input
            type="text"
            value={src.name}
            onChange={(e) => updateSelectedName(e.target.value)}
          />
        </label>
        <label className="field">
          <span>X, м</span>
          <input
            type="number"
            step={0.1}
            value={round3(src.position.x)}
            onChange={(e) =>
              updateSourcePosition(
                Number(e.target.value),
                src.position.y,
                src.position.z,
              )
            }
          />
        </label>
        <label className="field">
          <span>Y, м</span>
          <input
            type="number"
            step={0.1}
            value={round3(src.position.y)}
            onChange={(e) =>
              updateSourcePosition(
                src.position.x,
                Number(e.target.value),
                src.position.z,
              )
            }
          />
        </label>
        <label className="field">
          <span>Z, м</span>
          <input
            type="number"
            step={0.1}
            value={round3(src.position.z)}
            onChange={(e) =>
              updateSourcePosition(
                src.position.x,
                src.position.y,
                Number(e.target.value),
              )
            }
          />
        </label>
        <label className="field">
          <span>Lw (все полосы), дБ</span>
          <input
            type="number"
            step={1}
            value={lw0 ?? 90}
            onChange={(e) => updateSourceLw(Number(e.target.value))}
          />
        </label>
        <p className="props-meta">
          Полосы: {STANDARD_BANDS_HZ.join(", ")} Гц · Lw ≠ Lp
        </p>
      </aside>
    );
  }

  const wp = model.workplaces.find((w) => w.id === selection.id);
  if (!wp) return null;
  return (
    <aside className="props-panel" aria-label="Свойства рабочего места">
      <h3 className="props-title">Рабочее место</h3>
      <label className="field">
        <span>Имя</span>
        <input
          type="text"
          value={wp.name}
          onChange={(e) => updateSelectedName(e.target.value)}
        />
      </label>
      <label className="field">
        <span>X, м</span>
        <input
          type="number"
          step={0.1}
          value={round3(wp.position.x)}
          onChange={(e) =>
            updateWorkplacePosition(
              Number(e.target.value),
              wp.position.y,
              wp.position.z,
            )
          }
        />
      </label>
      <label className="field">
        <span>Y, м</span>
        <input
          type="number"
          step={0.1}
          value={round3(wp.position.y)}
          onChange={(e) =>
            updateWorkplacePosition(
              wp.position.x,
              Number(e.target.value),
              wp.position.z,
            )
          }
        />
      </label>
      <label className="field">
        <span>Высота приёмника Z, м</span>
        <input
          type="number"
          step={0.1}
          value={round3(wp.position.z)}
          onChange={(e) =>
            updateWorkplacePosition(
              wp.position.x,
              wp.position.y,
              Number(e.target.value),
            )
          }
        />
      </label>
    </aside>
  );
}

function round3(n: number): number {
  return Math.round(n * 1000) / 1000;
}
