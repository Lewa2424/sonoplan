import {
  createUuid,
  type AbsorptionBand,
  type MaterialVersion,
  type RoomSurfaceKind,
} from "@sonoplan/domain";
import { STANDARD_BANDS_HZ } from "./factoryModel";

/**
 * Типовые табличные α (не измерения конкретного объекта → estimated).
 * Источник: таблица «Absorption coefficients», akustik.ua
 * (https://www.acoustic.ua/st/web_absorption_data_eng.pdf; данные BRE),
 * строка таблицы — в `sourceRow`.
 */
export const MATERIAL_CATALOG_VERSION = "mvp-2";

/** α в октавах 125, 250, 500, 1000, 2000, 4000 Гц. */
type Alpha6 = readonly [number, number, number, number, number, number];

export interface MaterialCatalogEntry {
  readonly catalogKey: string;
  readonly nameRu: string;
  readonly alphaOctaves: Alpha6;
  readonly sourceRow: string;
  /** Где материал уместен; пустой — везде. */
  readonly surfaces: readonly RoomSurfaceKind[];
}

export const MATERIAL_CATALOG: readonly MaterialCatalogEntry[] = [
  {
    catalogKey: "concrete",
    nameRu: "Бетон гладкий / стяжка",
    alphaOctaves: [0.01, 0.01, 0.02, 0.02, 0.02, 0.05],
    sourceRow: "Smooth unpainted concrete",
    surfaces: [],
  },
  {
    catalogKey: "concrete_rough",
    nameRu: "Бетон шероховатый",
    alphaOctaves: [0.02, 0.03, 0.03, 0.03, 0.04, 0.07],
    sourceRow: "Rough concrete",
    surfaces: [],
  },
  {
    catalogKey: "polymer_floor",
    nameRu: "Полимерный пол / линолеум на бетоне",
    alphaOctaves: [0.02, 0.02, 0.03, 0.04, 0.04, 0.05],
    sourceRow: "Linoleum or vinyl stuck to concrete",
    surfaces: ["floor"],
  },
  {
    catalogKey: "brick",
    nameRu: "Кирпичная кладка",
    alphaOctaves: [0.02, 0.03, 0.03, 0.04, 0.05, 0.07],
    sourceRow: "Smooth brickwork with flush pointing",
    surfaces: ["walls"],
  },
  {
    catalogKey: "plaster",
    nameRu: "Штукатурка по кладке",
    alphaOctaves: [0.02, 0.02, 0.03, 0.04, 0.05, 0.05],
    sourceRow: "Lime cement plaster on masonry wall",
    surfaces: ["walls", "ceiling"],
  },
  {
    catalogKey: "plasterboard",
    nameRu: "ГКЛ на каркасе (100 мм воздух)",
    alphaOctaves: [0.3, 0.12, 0.08, 0.06, 0.06, 0.05],
    sourceRow: "Plasterboard on frame, 100mm airspace",
    surfaces: ["walls", "ceiling"],
  },
  {
    catalogKey: "glass",
    nameRu: "Остекление 6 мм",
    alphaOctaves: [0.1, 0.06, 0.04, 0.03, 0.02, 0.02],
    sourceRow: "6mm glass",
    surfaces: ["walls"],
  },
  {
    catalogKey: "metal_sheet",
    nameRu: "Профлист / стальной настил",
    alphaOctaves: [0.13, 0.09, 0.08, 0.09, 0.11, 0.11],
    sourceRow: "Steel decking",
    surfaces: ["walls", "ceiling"],
  },
  {
    catalogKey: "steel_deck_perforated",
    nameRu: "Перфорированный профнастил (кровля)",
    alphaOctaves: [0.3, 0.7, 0.85, 0.9, 0.7, 0.65],
    sourceRow: "Perforated underside of structural steel decking",
    surfaces: ["ceiling"],
  },
  {
    catalogKey: "wood_panel",
    nameRu: "Деревянная обшивка (25 мм воздух)",
    alphaOctaves: [0.3, 0.2, 0.15, 0.1, 0.1, 0.05],
    sourceRow: "Plywood, hardwood panels over 25mm airspace on solid backing",
    surfaces: ["walls", "ceiling"],
  },
  {
    catalogKey: "mineral_wool",
    nameRu: "Минвата 50 мм на стене",
    alphaOctaves: [0.11, 0.6, 0.96, 0.94, 0.92, 0.82],
    sourceRow: "Rock wool 50mm, 60 kg/m3 direct to masonry",
    surfaces: ["walls", "ceiling"],
  },
  {
    catalogKey: "mineral_wool_ceiling",
    nameRu: "Акустический потолок, минвата (180 мм)",
    alphaOctaves: [0.42, 0.72, 0.83, 0.88, 0.89, 0.8],
    sourceRow: "Mineral wool tiles, 180mm airspace",
    surfaces: ["ceiling"],
  },
  {
    catalogKey: "carpet",
    nameRu: "Ковролин на войлоке",
    alphaOctaves: [0.08, 0.08, 0.3, 0.6, 0.75, 0.8],
    sourceRow: "9mm pile carpet, tufted on felt underlay",
    surfaces: ["floor"],
  },
] as const;

/** Значения по умолчанию для нового цеха. */
export const DEFAULT_SURFACE_MATERIAL_KEYS: Readonly<Record<RoomSurfaceKind, string>> = {
  floor: "concrete",
  walls: "brick",
  ceiling: "metal_sheet",
};

export function materialByKey(
  catalogKey: string,
): MaterialCatalogEntry | undefined {
  return MATERIAL_CATALOG.find((m) => m.catalogKey === catalogKey);
}

export function materialsForSurface(
  surface: RoomSurfaceKind,
): readonly MaterialCatalogEntry[] {
  return MATERIAL_CATALOG.filter(
    (m) => m.surfaces.length === 0 || m.surfaces.includes(surface),
  );
}

const TABLE_BANDS_HZ = [125, 250, 500, 1000, 2000, 4000] as const;

/**
 * Таблица даёт 125–4000 Гц; 63 Гц и 8 кГц приняты равными крайним октавам
 * (125 и 4000 Гц) — экстраполяция, а не данные таблицы.
 */
function bandsFromOctaves(alpha: Alpha6): AbsorptionBand[] {
  const byHz = new Map<number, number>(TABLE_BANDS_HZ.map((hz, i) => [hz, alpha[i]!]));
  byHz.set(63, alpha[0]);
  byHz.set(8000, alpha[5]);
  return STANDARD_BANDS_HZ.map((bandHz) => ({
    bandHz,
    alpha: byHz.get(bandHz)!,
    nullReason: null,
  }));
}

/** Снимок MaterialVersion для ревизии (каталог не меняет старые ревизии молча). */
export function createMaterialVersionFromCatalog(
  catalogKey: string,
): MaterialVersion {
  const entry = materialByKey(catalogKey);
  if (!entry) throw new Error(`Unknown material catalogKey: ${catalogKey}`);
  return {
    id: createUuid(),
    catalogKey: entry.catalogKey,
    name: entry.nameRu,
    version: MATERIAL_CATALOG_VERSION,
    absorptionByBand: bandsFromOctaves(entry.alphaOctaves),
    estimated: true,
  };
}
