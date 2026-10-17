import { stripClosingDuplicate } from "./geometry.js";
import type {
  FloorVertex,
  MaterialVersion,
  ModelSnapshot,
  Room,
  RoomSurfaceKind,
} from "./types.js";

export const ROOM_SURFACE_KINDS: readonly RoomSurfaceKind[] = [
  "floor",
  "walls",
  "ceiling",
];

export function polygonAreaAndPerimeter(ring: readonly FloorVertex[]): {
  area: number;
  perimeter: number;
} {
  let twiceArea = 0;
  let perimeter = 0;
  for (let i = 0; i < ring.length; i++) {
    const a = ring[i]!;
    const b = ring[(i + 1) % ring.length]!;
    twiceArea += a.x * b.y - b.x * a.y;
    perimeter += Math.hypot(b.x - a.x, b.y - a.y);
  }
  return { area: Math.abs(twiceArea) / 2, perimeter };
}

/** Площади групп ограждений, м²; null — высота или контур неизвестны. */
export function roomSurfaceAreasM2(
  room: Room,
): Readonly<Record<RoomSurfaceKind, number>> | null {
  const height = room.heightM.value;
  if (height === null || !Number.isFinite(height) || height <= 0) return null;
  const ring = stripClosingDuplicate(room.floorContour);
  if (ring.length < 3) return null;
  const { area, perimeter } = polygonAreaAndPerimeter(ring);
  if (!(area > 0)) return null;
  return { floor: area, walls: perimeter * height, ceiling: area };
}

/** Материал группы ограждений; null — не назначен или ссылка не найдена. */
export function roomSurfaceMaterial(
  model: ModelSnapshot,
  room: Room,
  surface: RoomSurfaceKind,
): MaterialVersion | null {
  const id = room.surfaceMaterials[surface];
  if (id === null) return null;
  return model.materials.find((m) => m.id === id) ?? null;
}
