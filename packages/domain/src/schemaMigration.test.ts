import { describe, expect, it } from "vitest";
import { buildDiffuseFieldInput } from "./diffuseFieldEstimate.js";
import { UnsupportedSchemaVersionError, migrateModelSnapshot } from "./schemaMigration.js";
import { parseModelSnapshot } from "./snapshot.js";

const ROOM = "00000000-0000-4000-8000-000000000001";
const MAT = "00000000-0000-4000-8000-000000000002";
const OTHER = "00000000-0000-4000-8000-000000000003";

function legacyModel(materialVersionId: string | null, materials = [MAT]) {
  return {
    schemaVersion: "1.0",
    rooms: [
      {
        id: ROOM,
        floorContour: [
          { x: 0, y: 0 },
          { x: 10, y: 0 },
          { x: 10, y: 10 },
          { x: 0, y: 10 },
          { x: 0, y: 0 },
        ],
        heightM: { value: 5, unit: "m" },
        materialVersionId,
        materialNullReason: null,
      },
    ],
    sources: [
      {
        id: "00000000-0000-4000-8000-000000000010",
        name: "s",
        position: { x: 5, y: 5, z: 1.5 },
        powerSpectrumLw: [{ bandHz: 1000, level: { value: 90, unit: "dB" } }],
        directivityId: null,
        weight: null,
      },
    ],
    workplaces: [],
    materials: materials.map((id, i) => ({
      id,
      catalogKey: "k",
      name: "m",
      version: "mvp-1",
      estimated: true,
      absorptionByBand: [{ bandHz: 1000, alpha: 0.1 * (i + 1) }],
    })),
    solids: [],
  };
}

describe("schema migration 1.0 → 1.1", () => {
  it("assigns the single room material to floor, walls and ceiling", () => {
    const m = migrateModelSnapshot(legacyModel(OTHER, [MAT, OTHER]));
    expect(m.schemaVersion).toBe("1.1");
    expect(m.rooms[0]!.surfaceMaterials).toEqual({
      floor: OTHER,
      walls: OTHER,
      ceiling: OTHER,
    });
    expect("materialVersionId" in m.rooms[0]!).toBe(false);
  });

  it("keeps the 1.0 fallback (first material) so results do not change", () => {
    const m = migrateModelSnapshot(legacyModel(null, [MAT, OTHER]));
    expect(m.rooms[0]!.surfaceMaterials.walls).toBe(MAT);
    const dangling = migrateModelSnapshot(legacyModel("missing-id", [OTHER]));
    expect(dangling.rooms[0]!.surfaceMaterials.floor).toBe(OTHER);
  });

  it("leaves surfaces null when the 1.0 model has no material at all", () => {
    const m = migrateModelSnapshot(legacyModel(null, []));
    expect(m.rooms[0]!.surfaceMaterials).toEqual({ floor: null, walls: null, ceiling: null });
    expect(buildDiffuseFieldInput(m)).toEqual({ ok: false, reason: "no_material" });
  });

  it("migrated 1.0 estimate equals the single-material estimate", () => {
    const r = buildDiffuseFieldInput(migrateModelSnapshot(legacyModel(MAT)));
    if (!r.ok) throw new Error(r.reason);
    // S = 400 м², α = 0.1 → R = 400·0.1/0.9.
    expect(r.input.roomConstantByBandHz.get(1000)).toBeCloseTo(400 / 9, 9);
  });

  it("treats a model without schemaVersion as 1.0", () => {
    const { schemaVersion: _v, ...noVersion } = legacyModel(MAT);
    expect(migrateModelSnapshot(noVersion).rooms[0]!.surfaceMaterials.ceiling).toBe(MAT);
  });

  it("normalizes incomplete 1.1 surfaceMaterials to explicit null", () => {
    const m = migrateModelSnapshot({
      ...legacyModel(MAT),
      schemaVersion: "1.1",
      rooms: [{ id: ROOM, floorContour: [], heightM: { value: 5, unit: "m" }, surfaceMaterials: { floor: MAT } }],
    });
    expect(m.rooms[0]!.surfaceMaterials).toEqual({ floor: MAT, walls: null, ceiling: null });
  });

  it("rejects unknown versions instead of guessing", () => {
    expect(() => migrateModelSnapshot({ ...legacyModel(MAT), schemaVersion: "2.0" })).toThrow(
      UnsupportedSchemaVersionError,
    );
  });

  it("parseModelSnapshot migrates 1.0 and still requires an explicit version", () => {
    const parsed = parseModelSnapshot(JSON.stringify(legacyModel(MAT)));
    expect(parsed.schemaVersion).toBe("1.1");
    const { schemaVersion: _v, ...noVersion } = legacyModel(MAT);
    expect(() => parseModelSnapshot(JSON.stringify(noVersion))).toThrow(
      UnsupportedSchemaVersionError,
    );
  });
});
