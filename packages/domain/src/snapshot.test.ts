import { describe, expect, it } from "vitest";
import { createUuid } from "./uuid.js";
import {
  computeSnapshotHash,
  parseModelSnapshot,
  serializeModelSnapshot,
} from "./snapshot.js";
import { validateModel } from "./validate.js";
import type { ModelSnapshot } from "./types.js";
import { PROJECT_SCHEMA_VERSION } from "./types.js";

function sampleSnapshot(overrides: Partial<ModelSnapshot> = {}): ModelSnapshot {
  const roomId = createUuid();
  const sourceId = createUuid();
  const materialId = createUuid();
  const workplaceId = createUuid();

  const base: ModelSnapshot = {
    schemaVersion: PROJECT_SCHEMA_VERSION,
    rooms: [
      {
        id: roomId,
        floorContour: [
          { x: 0, y: 0 },
          { x: 10, y: 0 },
          { x: 10, y: 6 },
          { x: 0, y: 6 },
          { x: 0, y: 0 },
        ],
        heightM: { value: 4, unit: "m" },
        surfaceMaterials: { floor: materialId, walls: materialId, ceiling: materialId },
      },
    ],
    sources: [
      {
        id: sourceId,
        name: "Fan",
        position: { x: 2, y: 2, z: 1.2 },
        powerSpectrumLw: [
          { bandHz: 500, level: { value: 85, unit: "dB" } },
          { bandHz: 1000, level: { value: 82, unit: "dB" } },
        ],
        directivityId: null,
        weight: null,
        weightNullReason: "not_applicable",
      },
    ],
    workplaces: [
      {
        id: workplaceId,
        name: "WP-1",
        kind: "point",
        position: { x: 8, y: 4, z: 0 },
        receiverHeightM: { value: 1.5, unit: "m" },
        scheduleId: null,
      },
    ],
    materials: [
      {
        id: materialId,
        catalogKey: "concrete",
        name: "Бетон",
        version: "1",
        absorptionByBand: [{ bandHz: 500, alpha: 0.02 }],
        estimated: false,
      },
    ],
    solids: [],
  };

  return { ...base, ...overrides };
}

describe("snapshot serialize / hash", () => {
  it("round-trips without loss", () => {
    const snap = sampleSnapshot();
    const json = serializeModelSnapshot(snap);
    const back = parseModelSnapshot(json);
    expect(back).toEqual(snap);
    expect(computeSnapshotHash(back)).toBe(computeSnapshotHash(snap));
  });

  it("hash is stable and ignores key order via canonical JSON", () => {
    const a = sampleSnapshot();
    const b = parseModelSnapshot(serializeModelSnapshot(a));
    expect(computeSnapshotHash(a)).toBe(computeSnapshotHash(b));
    expect(computeSnapshotHash(a)).toMatch(/^[0-9a-f]{64}$/);
  });

  it("validate ok for rectangular room + Lw source", () => {
    const result = validateModel(sampleSnapshot());
    expect(result.errors).toEqual([]);
  });

  it("validate blocks missing Lw spectrum", () => {
    const snap = sampleSnapshot();
    const source = {
      ...snap.sources[0]!,
      powerSpectrumLw: [],
    };
    const result = validateModel({ ...snap, sources: [source] });
    expect(result.errors.some((e) => e.code === "source_spectrum_missing")).toBe(
      true,
    );
  });

  it("validate warns on estimated material", () => {
    const snap = sampleSnapshot();
    const mat = { ...snap.materials[0]!, estimated: true };
    const result = validateModel({ ...snap, materials: [mat] });
    expect(result.warnings.some((w) => w.code === "material_estimated")).toBe(
      true,
    );
  });

  it("validate blocks a room surface without material (α unknown ≠ 0)", () => {
    const snap = sampleSnapshot();
    const room = snap.rooms[0]!;
    const result = validateModel({
      ...snap,
      rooms: [{ ...room, surfaceMaterials: { ...room.surfaceMaterials, ceiling: null } }],
    });
    const hits = result.errors.filter((e) => e.code === "room_surface_material_missing");
    expect(hits.map((e) => e.path)).toEqual([`rooms/${room.id}/surfaceMaterials/ceiling`]);
  });

  it("validate blocks source inside solid", () => {
    const snap = sampleSnapshot();
    const solidId = createUuid();
    const result = validateModel({
      ...snap,
      solids: [
        {
          id: solidId,
          name: "Machine body",
          floorContour: [
            { x: 1, y: 1 },
            { x: 3, y: 1 },
            { x: 3, y: 3 },
            { x: 1, y: 3 },
            { x: 1, y: 1 },
          ],
          baseZM: 0,
          heightM: { value: 2, unit: "m" },
        },
      ],
    });
    expect(result.errors.some((e) => e.code === "source_inside_solid")).toBe(
      true,
    );
  });
});
