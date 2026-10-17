import { pointInPolygon, validateFloorContour } from "./geometry.js";
import { ROOM_SURFACE_KINDS, roomSurfaceMaterial } from "./roomSurfaces.js";
import type {
  ModelSnapshot,
  Source,
  ValidationIssue,
} from "./types.js";
import type { PowerLevelUnit, PressureLevelUnit } from "./units.js";

const STANDARD_BANDS_HZ = [63, 125, 250, 500, 1000, 2000, 4000, 8000] as const;

/**
 * Lw ≠ Lp: unit спектра мощности не может быть dBA (A-коррекция — отдельно к полосам).
 * PowerLevelUnit допускает только "dB".
 */
export function isLwUnit(unit: string): unit is PowerLevelUnit {
  return unit === "dB";
}

export function isLpUnit(unit: string): unit is PressureLevelUnit {
  return unit === "dB" || unit === "dBA";
}

function sourceHasUsableSpectrum(source: Source): boolean {
  if (source.powerSpectrumLw.length === 0) {
    return false;
  }
  return source.powerSpectrumLw.some(
    (band) => band.level.value !== null && Number.isFinite(band.level.value),
  );
}

function sourceInsideSolid(
  source: Source,
  snapshot: ModelSnapshot,
): { solidId: string; solidName: string } | null {
  for (const solid of snapshot.solids) {
    const h = solid.heightM.value;
    if (h === null || !Number.isFinite(h) || h <= 0) {
      continue;
    }
    const z0 = solid.baseZM;
    const z1 = z0 + h;
    const xyInside = pointInPolygon(
      { x: source.position.x, y: source.position.y },
      solid.floorContour,
    );
    if (xyInside && source.position.z >= z0 - 1e-9 && source.position.z <= z1 + 1e-9) {
      return { solidId: solid.id, solidName: solid.name };
    }
  }
  return null;
}

/**
 * Валидация снимка модели.
 * Блокирующие (error): незамкнутый контур, самопересечение, источник в solid,
 * отсутствующий спектр Lw, неверный unit Lw, ограждение без материала.
 * Warning: оценочные свойства материалов.
 */
export function validateModel(snapshot: ModelSnapshot): {
  errors: ValidationIssue[];
  warnings: ValidationIssue[];
} {
  const errors: ValidationIssue[] = [];
  const warnings: ValidationIssue[] = [];

  for (const room of snapshot.rooms) {
    const contourErrors = validateFloorContour(room.floorContour);
    for (const ce of contourErrors) {
      errors.push({
        code: ce.code,
        severity: "error",
        message: ce.message,
        path: `rooms/${room.id}/floorContour`,
        entityId: room.id,
      });
    }
    if (room.heightM.value === null) {
      errors.push({
        code: "room_height_unknown",
        severity: "error",
        message: room.heightM.nullReason ?? "Room height is unknown (null ≠ 0)",
        path: `rooms/${room.id}/heightM`,
        entityId: room.id,
      });
    }
    for (const surface of ROOM_SURFACE_KINDS) {
      if (!roomSurfaceMaterial(snapshot, room, surface)) {
        errors.push({
          code: "room_surface_material_missing",
          severity: "error",
          message: `Room ${surface} has no material (α unknown ≠ 0)`,
          path: `rooms/${room.id}/surfaceMaterials/${surface}`,
          entityId: room.id,
        });
      }
    }
  }

  for (const source of snapshot.sources) {
    for (const band of source.powerSpectrumLw) {
      if (!isLwUnit(band.level.unit)) {
        errors.push({
          code: "source_spectrum_not_lw",
          severity: "error",
          message: `Source spectrum must be Lw (unit dB), got ${band.level.unit}; Lw ≠ Lp`,
          path: `sources/${source.id}/powerSpectrumLw`,
          entityId: source.id,
        });
        break;
      }
    }
    if (!sourceHasUsableSpectrum(source)) {
      errors.push({
        code: "source_spectrum_missing",
        severity: "error",
        message: "Source has no usable Lw spectrum bands",
        path: `sources/${source.id}/powerSpectrumLw`,
        entityId: source.id,
      });
    }
    const hit = sourceInsideSolid(source, snapshot);
    if (hit) {
      errors.push({
        code: "source_inside_solid",
        severity: "error",
        message: `Source is inside solid "${hit.solidName}"`,
        path: `sources/${source.id}/position`,
        entityId: source.id,
      });
    }
  }

  for (const material of snapshot.materials) {
    if (material.estimated) {
      warnings.push({
        code: "material_estimated",
        severity: "warning",
        message: `Material "${material.name}" uses estimated properties`,
        path: `materials/${material.id}`,
        entityId: material.id,
      });
    }
  }

  void STANDARD_BANDS_HZ;
  return { errors, warnings };
}

export function validationOk(result: {
  errors: ValidationIssue[];
}): boolean {
  return result.errors.length === 0;
}
