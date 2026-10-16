import { createUuid, type AbsorptionBand, type MaterialVersion } from "@sonoplan/domain";
import { STANDARD_BANDS_HZ } from "./factoryModel";

/** Каталог покрытий MVP: оценочные α (estimated), не лабораторные. */
export interface MaterialCatalogEntry {
  readonly catalogKey: string;
  readonly nameRu: string;
  /** α по октавам STANDARD_BANDS_HZ; одна константа → одинаково на все полосы. */
  readonly alphaFlat: number;
}

export const MATERIAL_CATALOG: readonly MaterialCatalogEntry[] = [
  { catalogKey: "concrete", nameRu: "Бетон / стяжка", alphaFlat: 0.02 },
  { catalogKey: "plaster", nameRu: "Штукатурка", alphaFlat: 0.03 },
  { catalogKey: "brick", nameRu: "Кирпич", alphaFlat: 0.04 },
  { catalogKey: "metal_sheet", nameRu: "Листовой металл", alphaFlat: 0.05 },
  { catalogKey: "wood_panel", nameRu: "Деревянная обшивка", alphaFlat: 0.1 },
  { catalogKey: "mineral_wool", nameRu: "Минвата / акустическая плита", alphaFlat: 0.7 },
  { catalogKey: "carpet", nameRu: "Ковролин", alphaFlat: 0.35 },
] as const;

export function materialByKey(
  catalogKey: string,
): MaterialCatalogEntry | undefined {
  return MATERIAL_CATALOG.find((m) => m.catalogKey === catalogKey);
}

function bandsFromAlpha(alpha: number): AbsorptionBand[] {
  return STANDARD_BANDS_HZ.map((bandHz) => ({
    bandHz,
    alpha,
    nullReason: null,
  }));
}

/** Снимок MaterialVersion для ревизии (каталог не меняет старые ревизии молча). */
export function createMaterialVersionFromCatalog(
  catalogKey: string,
): MaterialVersion {
  const entry = materialByKey(catalogKey) ?? MATERIAL_CATALOG[0]!;
  return {
    id: createUuid(),
    catalogKey: entry.catalogKey,
    name: entry.nameRu,
    version: "mvp-1",
    absorptionByBand: bandsFromAlpha(entry.alphaFlat),
    estimated: true,
  };
}
