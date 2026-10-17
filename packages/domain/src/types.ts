import type { Uuid } from "./uuid.js";
import type { Quantity, LengthUnit, PowerLevelUnit } from "./units.js";
import type { ProjectPoint3 } from "./coordinates.js";

/** Версия схемы документа проекта (контракты / миграции). */
export const PROJECT_SCHEMA_VERSION = "1.1" as const;
export type ProjectSchemaVersion = typeof PROJECT_SCHEMA_VERSION;
/**
 * Версии, которые читаются через миграцию (`migrateModelSnapshot`).
 * 1.0: один `room.materialVersionId` на все ограждения.
 */
export const LEGACY_PROJECT_SCHEMA_VERSIONS = ["1.0"] as const;
export type LegacyProjectSchemaVersion =
  (typeof LEGACY_PROJECT_SCHEMA_VERSIONS)[number];

export type UtcIsoDateTime = string;

export interface Project {
  readonly id: Uuid;
  readonly ownerId: Uuid;
  readonly name: string;
  readonly accessPolicy: string;
  /** Текущая опубликованная/рабочая ревизия; null если ещё нет. */
  readonly currentRevisionId: Uuid | null;
  readonly schemaVersion: ProjectSchemaVersion;
}

export interface Revision {
  readonly id: Uuid;
  readonly projectId: Uuid;
  readonly parentId: Uuid | null;
  readonly schemaVersion: ProjectSchemaVersion;
  readonly authorId: Uuid;
  readonly createdAt: UtcIsoDateTime;
  /** SHA-256 канонического JSON модели; не зависит от имени проекта / камеры. */
  readonly snapshotHash: string;
}

/** Вершина контура комнаты в плоскости пола (Z задаётся отдельно высотой). */
export interface FloorVertex {
  readonly x: number;
  readonly y: number;
}

export interface Room {
  readonly id: Uuid;
  /**
   * Замкнутый контур пола: ≥3 уникальных вершин + явная замыкающая
   * (первая === последняя). Самопересечение — блокирующая ошибка валидации.
   */
  readonly floorContour: readonly FloorVertex[];
  /** Высота помещения, м. null ≠ 0. */
  readonly heightM: Quantity<LengthUnit>;
  /** Материал каждой группы ограждений; null = не назначен (не α=0). */
  readonly surfaceMaterials: RoomSurfaceMaterials;
  readonly materialNullReason?: string | null;
}

/** Группы ограждений призматического помещения: пол, стены (все), потолок/кровля. */
export type RoomSurfaceKind = "floor" | "walls" | "ceiling";

export type RoomSurfaceMaterials = Readonly<Record<RoomSurfaceKind, Uuid | null>>;

/**
 * Минимальная версия материала каталога.
 * Обновление каталога не меняет уже сохранённую ревизию молча.
 */
export interface MaterialVersion {
  readonly id: Uuid;
  readonly catalogKey: string;
  readonly name: string;
  readonly version: string;
  /** α по октавным полосам; null + nullReason, не 0. */
  readonly absorptionByBand: readonly AbsorptionBand[];
  /**
   * Оценочные (не измеренные) свойства → warning при validate,
   * не блокирующая ошибка.
   */
  readonly estimated: boolean;
}

export interface AbsorptionBand {
  readonly bandHz: number;
  readonly alpha: number | null;
  readonly nullReason?: string | null;
}

/**
 * Упрощённое препятствие (solid) для проверки «источник внутри solid».
 * Контур в плоскости пола + высота от baseZM.
 */
export interface SolidObstacle {
  readonly id: Uuid;
  readonly name: string;
  readonly floorContour: readonly FloorVertex[];
  readonly baseZM: number;
  readonly heightM: Quantity<LengthUnit>;
}

export interface OctaveBandLevel {
  readonly bandHz: number;
  /**
   * Уровень звуковой мощности Lw в полосе (дБ re 1 pW).
   * Не Lp: PressureLevelUnit сюда не допускается.
   * null с причиной, если неизвестен — не подставлять 0.
   */
  readonly level: Quantity<PowerLevelUnit>;
}

/**
 * Источник шума. Спектр — только Lw (`powerSpectrumLw`), не Lp.
 * Lw ≠ Lp: нельзя складывать дБ арифметически и подменять мощность давлением.
 */
export interface Source {
  readonly id: Uuid;
  readonly name: string;
  /** Позиция источника в координатах проекта. */
  readonly position: ProjectPoint3;
  /** Спектр Lw по полосам; пустой / все null → блокирующая ошибка validate. */
  readonly powerSpectrumLw: readonly OctaveBandLevel[];
  readonly directivityId: Uuid | null;
  readonly weight: number | null;
  readonly weightNullReason?: string | null;
}

export type WorkplaceKind = "point" | "area";

/** Рабочее место / приёмник. */
export interface Workplace {
  readonly id: Uuid;
  readonly name: string;
  readonly kind: WorkplaceKind;
  readonly position: ProjectPoint3;
  /** Высота приёмника над полом, м (часто 1.5); null с причиной. */
  readonly receiverHeightM: Quantity<LengthUnit>;
  readonly scheduleId: Uuid | null;
}

/**
 * Неизменяемый снимок модели для ревизии (без имени проекта / камеры).
 * snapshotHash = SHA-256(canonicalJson(payload)).
 */
export interface ModelSnapshot {
  readonly schemaVersion: ProjectSchemaVersion;
  readonly rooms: readonly Room[];
  readonly sources: readonly Source[];
  readonly workplaces: readonly Workplace[];
  readonly materials: readonly MaterialVersion[];
  readonly solids: readonly SolidObstacle[];
}

/** Изменяемый черновик проекта (draft body). */
export interface ProjectDraft {
  readonly schemaVersion: ProjectSchemaVersion;
  readonly name: string;
  readonly model: ModelSnapshot;
}

export type ValidationSeverity = "error" | "warning";

export interface ValidationIssue {
  readonly code: string;
  readonly severity: ValidationSeverity;
  readonly message: string;
  readonly path?: string;
  readonly entityId?: Uuid;
}
