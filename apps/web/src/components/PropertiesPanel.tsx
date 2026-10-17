import { useState } from "react";
import {
  ROOM_SURFACE_KINDS,
  roomSurfaceMaterial,
  totalLwA,
  type MaterialVersion,
  type RoomSurfaceKind,
} from "@sonoplan/domain";
import {
  contourVertexAngles,
  formatAngleDeg,
} from "../model/contourHelpers";
import { EQUIPMENT_CATALOG, SOLID_CATALOG } from "../model/equipmentCatalog";
import {
  MATERIAL_CATALOG_VERSION,
  materialByKey,
  materialsForSurface,
} from "../model/materialCatalog";
import { ru } from "../i18n/ru";
import { useEditorStore } from "../store/editorStore";

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
  const updateSourceLwA = useEditorStore((s) => s.updateSourceLwA);
  const updateSourcePosition = useEditorStore((s) => s.updateSourcePosition);
  const updateWorkplacePosition = useEditorStore(
    (s) => s.updateWorkplacePosition,
  );
  const updateSolidHeight = useEditorStore((s) => s.updateSolidHeight);
  const setRoomSurfaceMaterial = useEditorStore((s) => s.setRoomSurfaceMaterial);
  const setPendingEquipment = useEditorStore((s) => s.setPendingEquipment);
  const setPendingSolid = useEditorStore((s) => s.setPendingSolid);
  const pendingEquipmentKey = useEditorStore((s) => s.pendingEquipmentKey);
  const pendingSolidKind = useEditorStore((s) => s.pendingSolidKind);
  const placeWithWorkplace = useEditorStore((s) => s.placeWithWorkplace);
  const setPlaceWithWorkplace = useEditorStore((s) => s.setPlaceWithWorkplace);
  const markDirty = useEditorStore((s) => s.markDirty);

  const room = model.rooms[0];

  const coatingsBlock = (
    <div className="props-block">
      <h4 className="props-subtitle">{ru.model.coatings}</h4>
      <p className="props-meta">{ru.model.coatingsHint}</p>
      {room
        ? ROOM_SURFACE_KINDS.map((surface) => (
            <SurfaceMaterialField
              key={surface}
              surface={surface}
              material={roomSurfaceMaterial(model, room, surface)}
              onChange={(key) => setRoomSurfaceMaterial(surface, key)}
            />
          ))
        : null}
      <p className="props-meta">{ru.model.materialSource}</p>
    </div>
  );

  const placeBlock = (
    <div className="props-block">
      <h4 className="props-subtitle">{ru.model.equipment}</h4>
      <label className="field field--check">
        <input
          type="checkbox"
          checked={placeWithWorkplace}
          onChange={(e) => setPlaceWithWorkplace(e.target.checked)}
        />
        <span>{ru.model.placeWorkplaceNear}</span>
      </label>
      <div className="props-chip-row">
        {EQUIPMENT_CATALOG.map((eq) => (
          <button
            key={eq.catalogKey}
            type="button"
            className={
              pendingEquipmentKey === eq.catalogKey
                ? "btn btn--active btn--chip"
                : "btn btn--chip"
            }
            onClick={() =>
              setPendingEquipment(
                pendingEquipmentKey === eq.catalogKey ? null : eq.catalogKey,
              )
            }
          >
            {eq.nameRu}
          </button>
        ))}
      </div>
      <h4 className="props-subtitle">{ru.model.obstacle}</h4>
      <p className="props-meta">{ru.model.solidsNote}</p>
      <div className="props-chip-row">
        {SOLID_CATALOG.map((s) => (
          <button
            key={s.kind}
            type="button"
            className={
              pendingSolidKind === s.kind
                ? "btn btn--active btn--chip"
                : "btn btn--chip"
            }
            onClick={() =>
              setPendingSolid(pendingSolidKind === s.kind ? null : s.kind)
            }
          >
            {s.nameRu}
          </button>
        ))}
      </div>
      {(pendingEquipmentKey || pendingSolidKind) && (
        <p className="plan-place-hint">Каснитесь плана для размещения</p>
      )}
    </div>
  );

  if (!selection) {
    return (
      <aside className="props-panel" aria-label="Свойства">
        <p className="props-empty">Выберите объект или разместите оборудование</p>
        {coatingsBlock}
        {placeBlock}
      </aside>
    );
  }

  if (selection.kind === "room") {
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
        {coatingsBlock}
        {placeBlock}
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
    const lwA = totalLwA(src.powerSpectrumLw);
    return (
      <aside className="props-panel" aria-label="Свойства источника">
        <h3 className="props-title">Оборудование / источник</h3>
        <p className="props-badge">Lw, дБ re 1 pW · Lw ≠ Lp</p>
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
          <span>{ru.model.lwTypical}</span>
          <input
            type="number"
            step={1}
            value={lwA === null ? "" : round1(lwA)}
            onChange={(e) => {
              const v = e.target.valueAsNumber;
              if (Number.isFinite(v)) updateSourceLwA(v);
            }}
          />
        </label>
        <p className="props-meta">{ru.model.lwFlatSpectrumNote}</p>
        <details className="props-details">
          <summary>{ru.model.spectrumAdvanced}</summary>
          <p className="props-meta">{ru.model.lwBandsLabel}</p>
          <ul className="props-angles">
            {src.powerSpectrumLw.map((b) => (
              <li key={b.bandHz}>
                {b.bandHz} Гц: {b.level.value === null ? "—" : round1(b.level.value)} дБ
              </li>
            ))}
          </ul>
        </details>
        <DeleteSelectedButton key={src.id} label={ru.model.deleteEquipment} />
        {placeBlock}
      </aside>
    );
  }

  if (selection.kind === "solid") {
    const solid = model.solids.find((s) => s.id === selection.id);
    if (!solid) return null;
    return (
      <aside className="props-panel" aria-label="Свойства препятствия">
        <h3 className="props-title">{solid.name}</h3>
        <p className="props-meta">{ru.model.solidsNote}</p>
        <label className="field">
          <span>Имя</span>
          <input
            type="text"
            value={solid.name}
            onChange={(e) => updateSelectedName(e.target.value)}
          />
        </label>
        <label className="field">
          <span>Высота, м</span>
          <input
            type="number"
            min={0.1}
            step={0.1}
            value={round3(solid.heightM.value ?? 2)}
            onChange={(e) => updateSolidHeight(Number(e.target.value))}
          />
        </label>
        <DeleteSelectedButton key={solid.id} label={ru.model.deleteObstacle} />
        {placeBlock}
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
      <DeleteSelectedButton key={wp.id} label={ru.model.deleteWorkplace} />
      {placeBlock}
    </aside>
  );
}

function DeleteSelectedButton({ label }: { label: string }) {
  const deleteSelected = useEditorStore((s) => s.deleteSelected);
  const [confirming, setConfirming] = useState(false);
  if (!confirming) {
    return (
      <button
        type="button"
        className="btn btn--warn props-delete"
        onClick={() => setConfirming(true)}
      >
        {label}
      </button>
    );
  }
  return (
    <div className="props-delete-row">
      <button
        type="button"
        className="btn btn--danger"
        autoFocus
        onClick={deleteSelected}
      >
        {ru.model.deleteConfirm}
      </button>
      <button type="button" className="btn" onClick={() => setConfirming(false)}>
        {ru.model.deleteCancel}
      </button>
    </div>
  );
}

function SurfaceMaterialField({
  surface,
  material,
  onChange,
}: {
  surface: RoomSurfaceKind;
  material: MaterialVersion | null;
  onChange: (catalogKey: string) => void;
}) {
  const options = materialsForSurface(surface);
  const inCatalog = material ? materialByKey(material.catalogKey) : undefined;
  const listed = material && options.some((m) => m.catalogKey === material.catalogKey);
  const alphas = material
    ? TABLE_BANDS_HZ.map((hz) => {
        const a = material.absorptionByBand.find((b) => b.bandHz === hz)?.alpha;
        return a === null || a === undefined ? "—" : a.toFixed(2);
      }).join(" / ")
    : null;
  return (
    <div className="props-surface">
      <label className="field">
        <span>{ru.model.surfaceLabel[surface]}</span>
        <select
          value={material?.catalogKey ?? ""}
          onChange={(e) => onChange(e.target.value)}
        >
          {material === null ? <option value="" disabled>—</option> : null}
          {material && !listed ? (
            <option value={material.catalogKey} disabled>
              {inCatalog?.nameRu ?? `${material.name} (${ru.model.materialOutsideCatalog})`}
            </option>
          ) : null}
          {options.map((m) => (
            <option key={m.catalogKey} value={m.catalogKey}>
              {m.nameRu}
            </option>
          ))}
        </select>
      </label>
      {alphas ? (
        <p className="props-meta">
          {ru.model.alphaOctavesLabel}: {alphas}
        </p>
      ) : null}
      {material && material.version !== MATERIAL_CATALOG_VERSION ? (
        <div className="props-surface-outdated">
          <p className="props-meta props-meta--warn">{ru.model.materialOutdated}</p>
          {inCatalog && listed ? (
            <button
              type="button"
              className="btn btn--chip"
              onClick={() => onChange(material.catalogKey)}
            >
              {ru.model.materialRefresh}
            </button>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

const TABLE_BANDS_HZ = [125, 250, 500, 1000, 2000, 4000] as const;

function round1(n: number): number {
  return Math.round(n * 10) / 10;
}

function round3(n: number): number {
  return Math.round(n * 1000) / 1000;
}
