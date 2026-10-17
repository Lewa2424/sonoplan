import { totalLwA, validateModel } from "@sonoplan/domain";
import { describe, expect, it } from "vitest";
import { lwSpectrumForEquipment } from "./equipmentCatalog";
import {
  STANDARD_BANDS_HZ,
  assignSurfaceMaterial,
  createOfflineDraft,
  ensureRoomSurfaceMaterials,
  parseDraftBody,
} from "./factoryModel";
import {
  MATERIAL_CATALOG,
  MATERIAL_CATALOG_VERSION,
  createMaterialVersionFromCatalog,
  materialsForSurface,
} from "./materialCatalog";

const MAT = "00000000-0000-4000-8000-000000000002";

function legacyDraftBody() {
  return {
    schemaVersion: "1.0",
    name: "Цех",
    model: {
      schemaVersion: "1.0",
      rooms: [
        {
          id: "00000000-0000-4000-8000-000000000001",
          floorContour: [
            { x: 0, y: 0 },
            { x: 20, y: 0 },
            { x: 20, y: 12 },
            { x: 0, y: 12 },
            { x: 0, y: 0 },
          ],
          heightM: { value: 6, unit: "m" },
          materialVersionId: MAT,
          materialNullReason: null,
        },
      ],
      sources: [],
      workplaces: [],
      materials: [
        {
          id: MAT,
          catalogKey: "carpet",
          name: "Ковролин",
          version: "mvp-1",
          estimated: true,
          absorptionByBand: STANDARD_BANDS_HZ.map((bandHz) => ({ bandHz, alpha: 0.35 })),
        },
      ],
      solids: [],
    },
  };
}

describe("material catalog", () => {
  it("covers all 8 model octaves with 63 Hz / 8 kHz taken from 125 Hz / 4 kHz", () => {
    for (const entry of MATERIAL_CATALOG) {
      const mat = createMaterialVersionFromCatalog(entry.catalogKey);
      expect(mat.absorptionByBand.map((b) => b.bandHz)).toEqual([...STANDARD_BANDS_HZ]);
      const at = (hz: number) => mat.absorptionByBand.find((b) => b.bandHz === hz)!.alpha;
      expect(at(63)).toBe(entry.alphaOctaves[0]);
      expect(at(8000)).toBe(entry.alphaOctaves[5]);
      for (const b of mat.absorptionByBand) {
        expect(b.alpha).toBeGreaterThan(0);
        expect(b.alpha).toBeLessThanOrEqual(1);
      }
      expect(mat.version).toBe(MATERIAL_CATALOG_VERSION);
      expect(mat.estimated).toBe(true);
    }
  });

  it("rejects unknown catalog keys instead of substituting concrete", () => {
    expect(() => createMaterialVersionFromCatalog("nope")).toThrow();
  });

  it("offers each surface at least one material", () => {
    for (const s of ["floor", "walls", "ceiling"] as const) {
      expect(materialsForSurface(s).length).toBeGreaterThan(1);
    }
  });
});

describe("surface materials", () => {
  it("new offline draft has a material on every surface and validates", () => {
    const { model } = createOfflineDraft("Цех");
    expect(model.schemaVersion).toBe("1.1");
    const s = model.rooms[0]!.surfaceMaterials;
    expect([s.floor, s.walls, s.ceiling].every((id) => id !== null)).toBe(true);
    expect(validateModel(model).errors).toEqual([]);
  });

  it("parseDraftBody migrates a 1.0 draft and keeps its stored α", () => {
    const draft = parseDraftBody(legacyDraftBody());
    expect(draft.schemaVersion).toBe("1.1");
    expect(draft.model.rooms[0]!.surfaceMaterials).toEqual({
      floor: MAT,
      walls: MAT,
      ceiling: MAT,
    });
    expect(draft.model.materials[0]!.absorptionByBand[0]!.alpha).toBe(0.35);
  });

  it("changing one surface keeps the others and drops unreferenced materials", () => {
    const migrated = parseDraftBody(legacyDraftBody()).model;
    const next = assignSurfaceMaterial(migrated, "ceiling", "mineral_wool_ceiling");
    const s = next.rooms[0]!.surfaceMaterials;
    expect(s.floor).toBe(MAT);
    expect(s.walls).toBe(MAT);
    expect(s.ceiling).not.toBe(MAT);
    expect(next.materials.map((m) => m.catalogKey).sort()).toEqual([
      "carpet",
      "mineral_wool_ceiling",
    ]);

    const all = assignSurfaceMaterial(
      assignSurfaceMaterial(next, "floor", "concrete"),
      "walls",
      "concrete",
    );
    const t = all.rooms[0]!.surfaceMaterials;
    expect(t.floor).toBe(t.walls);
    expect(all.materials.map((m) => m.catalogKey).sort()).toEqual([
      "concrete",
      "mineral_wool_ceiling",
    ]);
  });

  it("ensureRoomSurfaceMaterials fills only missing surfaces", () => {
    const migrated = parseDraftBody(legacyDraftBody()).model;
    const room = migrated.rooms[0]!;
    const holed = {
      ...migrated,
      rooms: [{ ...room, surfaceMaterials: { ...room.surfaceMaterials, walls: null } }],
    };
    const filled = ensureRoomSurfaceMaterials(holed);
    const s = filled.rooms[0]!.surfaceMaterials;
    expect(s.floor).toBe(MAT);
    expect(s.ceiling).toBe(MAT);
    expect(filled.materials.find((m) => m.id === s.walls)?.catalogKey).toBe("brick");
  });
});

describe("equipment Lw", () => {
  it("catalog level is the total LwA, not a per-octave level", () => {
    const { spectrum } = lwSpectrumForEquipment("lathe");
    expect(totalLwA(spectrum)).toBeCloseTo(95, 9);
    expect(spectrum[0]!.level.value!).toBeCloseTo(88.0, 1);
  });
});
