import { describe, expect, it } from "vitest";
import { planCutHeightM } from "./planCut.js";
import type { ModelSnapshot } from "./types.js";
import { asUuid } from "./uuid.js";

function id(n: number) {
  return asUuid(`00000000-0000-4000-8000-${String(n).padStart(12, "0")}`);
}

function snap(
  heightM: number | null,
  wps: readonly (readonly [z: number, receiverHeightM: number])[],
  sourceZs: readonly number[],
): ModelSnapshot {
  return {
    schemaVersion: "1.0",
    rooms: [
      {
        id: id(1),
        floorContour: [
          { x: 0, y: 0 },
          { x: 10, y: 0 },
          { x: 10, y: 8 },
          { x: 0, y: 8 },
          { x: 0, y: 0 },
        ],
        heightM: { value: heightM, unit: "m" },
        materialVersionId: null,
      },
    ],
    sources: sourceZs.map((z, i) => ({
      id: id(100 + i),
      name: `s${i}`,
      position: { x: 2 + i, y: 2, z },
      powerSpectrumLw: [{ bandHz: 1000, level: { value: 90, unit: "dB" } }],
      directivityId: null,
      weight: null,
    })),
    workplaces: wps.map(([z, rh], i) => ({
      id: id(200 + i),
      name: `w${i}`,
      kind: "point",
      position: { x: 5, y: 5, z },
      receiverHeightM: { value: rh, unit: "m" },
      scheduleId: null,
    })),
    materials: [],
    solids: [],
  };
}

describe("planCutHeightM — parity with SPPS export coupe z", () => {
  // Expected values produced by export_revision.compact_export_payload +
  // build_config_xml (same cases in engine/adapter/tests/test_export_revision.py).
  it.each([
    [6, [[0, 1.5], [0, 1.5]], [1.0], 1.5],
    [6, [[0, 1.5]], [1.5], 1.15],
    [6, [[0, 1.5]], [1.5, 1.2], 1.85],
    [6, [[0, 1.6], [1.2, 1.5]], [1.0, 1.75], 1.4],
    [6, [[0, 1.5]], [1.5, 1.15, 1.85, 0.8, 2.2], 0.25],
    [1.0, [[0, 1.5]], [0.5], 0.85],
  ] as const)("h=%s wps=%j sources=%j → %s m", (h, wps, srcs, expected) => {
    expect(planCutHeightM(snap(h, wps, srcs))).toBeCloseTo(expected, 9);
  });

  it("is null when the room height is unknown (not a default plane)", () => {
    expect(planCutHeightM(snap(null, [[0, 1.5]], [1]))).toBeNull();
  });
});
