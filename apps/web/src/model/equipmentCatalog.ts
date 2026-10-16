import type { OctaveBandLevel } from "@sonoplan/domain";
import { STANDARD_BANDS_HZ, uniformLwSpectrum } from "./factoryModel";

/**
 * Каталог оборудования MVP: оценочные Lw (дБ re 1 pW), не паспортные.
 * Полосы — октавы STANDARD_BANDS_HZ; flat = одинаковый уровень во всех.
 */
export interface EquipmentCatalogEntry {
  readonly catalogKey: string;
  readonly nameRu: string;
  /** Типовой Lw (все полосы), дБ. */
  readonly lwFlatDb: number;
  /** Смещение РМ от источника, м (для «добавить РМ рядом»). */
  readonly workplaceOffsetM: number;
}

export const EQUIPMENT_CATALOG: readonly EquipmentCatalogEntry[] = [
  {
    catalogKey: "lathe",
    nameRu: "Токарный станок",
    lwFlatDb: 95,
    workplaceOffsetM: 1.2,
  },
  {
    catalogKey: "milling",
    nameRu: "Фрезерный станок",
    lwFlatDb: 98,
    workplaceOffsetM: 1.2,
  },
  {
    catalogKey: "circular_saw",
    nameRu: "Циркулярка",
    lwFlatDb: 105,
    workplaceOffsetM: 1.0,
  },
  {
    catalogKey: "drill_press",
    nameRu: "Сверлильный станок",
    lwFlatDb: 90,
    workplaceOffsetM: 0.8,
  },
  {
    catalogKey: "industrial_vacuum",
    nameRu: "Промышленный пылесос",
    lwFlatDb: 100,
    workplaceOffsetM: 1.5,
  },
  {
    catalogKey: "compressor",
    nameRu: "Компрессор",
    lwFlatDb: 102,
    workplaceOffsetM: 1.5,
  },
  {
    catalogKey: "generic_machine",
    nameRu: "Оборудование (общее)",
    lwFlatDb: 92,
    workplaceOffsetM: 1.0,
  },
] as const;

export type SolidKind = "rack" | "cabinet" | "partition";

export interface SolidCatalogEntry {
  readonly kind: SolidKind;
  readonly nameRu: string;
  /** Размер прямоугольника по умолчанию, м (ширина × глубина). */
  readonly defaultWidthM: number;
  readonly defaultDepthM: number;
  readonly defaultHeightM: number;
}

export const SOLID_CATALOG: readonly SolidCatalogEntry[] = [
  {
    kind: "rack",
    nameRu: "Стеллаж",
    defaultWidthM: 2.0,
    defaultDepthM: 0.6,
    defaultHeightM: 2.5,
  },
  {
    kind: "cabinet",
    nameRu: "Шкаф",
    defaultWidthM: 1.2,
    defaultDepthM: 0.6,
    defaultHeightM: 2.0,
  },
  {
    kind: "partition",
    nameRu: "Перегородка",
    defaultWidthM: 0.15,
    defaultDepthM: 3.0,
    defaultHeightM: 2.5,
  },
] as const;

export function equipmentByKey(
  catalogKey: string,
): EquipmentCatalogEntry | undefined {
  return EQUIPMENT_CATALOG.find((e) => e.catalogKey === catalogKey);
}

export function solidByKind(kind: SolidKind): SolidCatalogEntry {
  return SOLID_CATALOG.find((s) => s.kind === kind) ?? SOLID_CATALOG[0]!;
}

export function lwSpectrumForEquipment(
  catalogKey: string,
): { name: string; spectrum: OctaveBandLevel[] } {
  const entry = equipmentByKey(catalogKey) ?? EQUIPMENT_CATALOG[EQUIPMENT_CATALOG.length - 1]!;
  return {
    name: entry.nameRu,
    spectrum: uniformLwSpectrum(entry.lwFlatDb),
  };
}

/** Для свёрнутого просмотра — список полос как строка. */
export function bandListLabel(): string {
  return STANDARD_BANDS_HZ.join(" ") + " Гц";
}
