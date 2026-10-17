import { describe, expect, it } from "vitest";
import {
  buildDiffuseFieldInput,
  estimateLpAt,
  estimateLpGrid,
} from "./diffuseFieldEstimate.js";
import type { ModelSnapshot, Source } from "./types.js";
import { asUuid } from "./uuid.js";

const ROOM_ID = asUuid("00000000-0000-4000-8000-000000000001");
const MAT_ID = asUuid("00000000-0000-4000-8000-000000000002");

function source(
  x: number,
  y: number,
  z: number,
  bands: Record<number, number | null>,
  n = 0,
): Source {
  return {
    id: asUuid(`00000000-0000-4000-8000-0000000001${String(n).padStart(2, "0")}`),
    name: `src${n}`,
    position: { x, y, z },
    powerSpectrumLw: Object.entries(bands).map(([hz, v]) => ({
      bandHz: Number(hz),
      level: { value: v, unit: "dB" as const },
    })),
    directivityId: null,
    weight: null,
  };
}

/** 10×10×5 м: A=100 м², P=40 м, S = 2·100 + 40·5 = 400 м². */
function model(
  sources: Source[],
  alphaByBand: Record<number, number | null>,
  contour = [
    { x: 0, y: 0 },
    { x: 10, y: 0 },
    { x: 10, y: 10 },
    { x: 0, y: 10 },
    { x: 0, y: 0 },
  ],
): ModelSnapshot {
  return {
    schemaVersion: "1.1",
    rooms: [
      {
        id: ROOM_ID,
        floorContour: contour,
        heightM: { value: 5, unit: "m" },
        surfaceMaterials: { floor: MAT_ID, walls: MAT_ID, ceiling: MAT_ID },
      },
    ],
    sources,
    workplaces: [],
    materials: [material(MAT_ID, alphaByBand)],
    solids: [],
  };
}

function material(id: ReturnType<typeof asUuid>, alphaByBand: Record<number, number | null>) {
  return {
    id,
    catalogKey: "test",
    name: "test",
    version: "1",
    estimated: true,
    absorptionByBand: Object.entries(alphaByBand).map(([hz, a]) => ({
      bandHz: Number(hz),
      alpha: a,
    })),
  };
}

const FLOOR_ID = asUuid("00000000-0000-4000-8000-000000000003");
const CEIL_ID = asUuid("00000000-0000-4000-8000-000000000004");

/** Пол / стены / потолок с разными α (стены — MAT_ID). */
function mixedModel(
  floor: Record<number, number | null>,
  walls: Record<number, number | null>,
  ceiling: Record<number, number | null>,
): ModelSnapshot {
  const base = model([source(5, 5, 1.5, { 500: 100, 1000: 100 })], walls);
  return {
    ...base,
    rooms: [
      {
        ...base.rooms[0]!,
        surfaceMaterials: { floor: FLOOR_ID, walls: MAT_ID, ceiling: CEIL_ID },
      },
    ],
    materials: [material(MAT_ID, walls), material(FLOOR_ID, floor), material(CEIL_ID, ceiling)],
  };
}

function inputOf(m: ModelSnapshot) {
  const r = buildDiffuseFieldInput(m);
  if (!r.ok) throw new Error(`unexpected ${r.reason}`);
  return r.input;
}

describe("diffuse field estimate", () => {
  it("matches hand-computed direct + reverberant level", () => {
    // R = 400·0.2/0.8 = 100 м²; r = 2 м:
    // 1/(4π·4) + 4/100 = 0.0198944 + 0.04 → 10·lg = −12.2263 → 87.774 дБ.
    const inp = inputOf(model([source(5, 5, 1.5, { 1000: 100 })], { 1000: 0.2 }));
    expect(inp.totalSurfaceM2).toBeCloseTo(400, 9);
    expect(inp.roomConstantByBandHz.get(1000)).toBeCloseTo(100, 9);
    expect(estimateLpAt(inp, 7, 5, 1.5, "Z")).toBeCloseTo(87.774, 2);
  });

  it("sums sources by energy, not arithmetically (+3.01 dB for two equal)", () => {
    const one = inputOf(model([source(5, 5, 1.5, { 1000: 90 })], { 1000: 0.2 }));
    const two = inputOf(
      model(
        [source(5, 5, 1.5, { 1000: 90 }, 0), source(5, 5, 1.5, { 1000: 90 }, 1)],
        { 1000: 0.2 },
      ),
    );
    const a = estimateLpAt(one, 8, 5, 1.5, "Z")!;
    const b = estimateLpAt(two, 8, 5, 1.5, "Z")!;
    expect(b - a).toBeCloseTo(10 * Math.log10(2), 6);
  });

  it("sums bands by energy without weighting under Z", () => {
    const single = inputOf(model([source(5, 5, 1.5, { 1000: 90 })], { 1000: 0.3 }));
    const both = inputOf(
      model([source(5, 5, 1.5, { 500: 90, 1000: 90 })], { 500: 0.3, 1000: 0.3 }),
    );
    expect(both.bandsHz).toEqual([500, 1000]);
    expect(
      estimateLpAt(both, 8, 5, 1.5, "Z")! - estimateLpAt(single, 8, 5, 1.5, "Z")!,
    ).toBeCloseTo(10 * Math.log10(2), 6);
  });

  it("applies A-weighting once per band before the energy sum", () => {
    // 125 Гц: A = −16.1; 1000 Гц: A = 0. Same Lw and α in both bands, so the
    // A-weighted total is Lz(one band) + 10·lg(10^(−1.61) + 1).
    const inp = inputOf(
      model([source(5, 5, 1.5, { 125: 90, 1000: 90 })], { 125: 0.3, 1000: 0.3 }),
    );
    const one = inputOf(model([source(5, 5, 1.5, { 1000: 90 })], { 1000: 0.3 }));
    const lz1 = estimateLpAt(one, 8, 5, 1.5, "Z")!;
    expect(estimateLpAt(inp, 8, 5, 1.5, "A")!).toBeCloseTo(
      lz1 + 10 * Math.log10(10 ** -1.61 + 1),
      6,
    );
    expect(estimateLpAt(inp, 8, 5, 1.5, "Z")! - lz1).toBeCloseTo(10 * Math.log10(2), 6);
  });

  it("refuses A-weighting for a non-nominal band instead of guessing", () => {
    const inp = inputOf(model([source(5, 5, 1.5, { 1100: 90 })], { 1100: 0.3 }));
    expect(() => estimateLpAt(inp, 8, 5, 1.5, "A")).toThrow(RangeError);
  });

  it("drops the reverberant term when alpha = 1 (free field)", () => {
    // 10·lg(1/(4π·4)) = −17.0127 → 82.987 дБ.
    const inp = inputOf(model([source(5, 5, 1.5, { 1000: 100 })], { 1000: 1 }));
    expect(estimateLpAt(inp, 7, 5, 1.5, "Z")).toBeCloseTo(82.987, 2);
  });

  it("clamps distance near the source instead of diverging", () => {
    const inp = inputOf(model([source(5, 5, 1.5, { 1000: 100 })], { 1000: 0.2 }));
    const atSource = estimateLpAt(inp, 5, 5, 1.5, "Z");
    expect(atSource).not.toBeNull();
    expect(atSource).toBeCloseTo(estimateLpAt(inp, 5.5, 5, 1.5, "Z")!, 9);
  });

  it("level decreases away from the source (responds to position)", () => {
    const inp = inputOf(model([source(2, 5, 1.5, { 1000: 95 })], { 1000: 0.1 }));
    const near = estimateLpAt(inp, 3, 5, 1.5, "A")!;
    const far = estimateLpAt(inp, 9, 5, 1.5, "A")!;
    expect(near).toBeGreaterThan(far);
  });

  it("reports why the estimate is unavailable instead of returning 0 dB", () => {
    expect(buildDiffuseFieldInput(model([], { 1000: 0.2 }))).toEqual({
      ok: false,
      reason: "no_sources",
    });
    // Lw known only at 500 Hz, α known only at 1000 Hz → no common band.
    expect(
      buildDiffuseFieldInput(model([source(5, 5, 1, { 500: 90 })], { 1000: 0.2, 500: null })),
    ).toEqual({ ok: false, reason: "no_common_bands" });
    expect(
      buildDiffuseFieldInput(model([source(5, 5, 1, { 1000: null })], { 1000: 0.2 })),
    ).toEqual({ ok: false, reason: "no_sources" });
  });

  it("weights alpha by surface area of floor, walls and ceiling", () => {
    // Пол 100 м²·0.1 + стены 200 м²·0.2 + потолок 100 м²·0.6 = 110 м² → ᾱ = 0.275.
    // R = 400·0.275/0.725 = 151.724 м².
    const inp = inputOf(mixedModel({ 1000: 0.1 }, { 1000: 0.2 }, { 1000: 0.6 }));
    expect(inp.roomConstantByBandHz.get(1000)).toBeCloseTo((400 * 0.275) / 0.725, 9);
  });

  it("drops a band unless every surface knows alpha there", () => {
    const inp = inputOf(
      mixedModel({ 500: 0.1, 1000: 0.1 }, { 500: 0.2, 1000: 0.2 }, { 1000: 0.6, 500: null }),
    );
    expect(inp.bandsHz).toEqual([1000]);
  });

  it("is unavailable when any surface has no material", () => {
    const base = model([source(5, 5, 1.5, { 1000: 90 })], { 1000: 0.2 });
    const noCeiling: ModelSnapshot = {
      ...base,
      rooms: [
        {
          ...base.rooms[0]!,
          surfaceMaterials: { floor: MAT_ID, walls: MAT_ID, ceiling: null },
        },
      ],
    };
    expect(buildDiffuseFieldInput(noCeiling)).toEqual({ ok: false, reason: "no_material" });
  });

  it("grid masks cells outside an L-shaped contour", () => {
    const L = [
      { x: 0, y: 0 },
      { x: 8, y: 0 },
      { x: 8, y: 3 },
      { x: 3, y: 3 },
      { x: 3, y: 7 },
      { x: 0, y: 7 },
      { x: 0, y: 0 },
    ];
    const inp = inputOf(model([source(1, 1, 1.5, { 1000: 90 })], { 1000: 0.2 }, L));
    const g = estimateLpGrid(inp, 1.5, "A", 1);
    expect(g.nx).toBe(8);
    expect(g.ny).toBe(7);
    expect(g.weighting).toBe("A");
    expect(g.lpDb[0 * g.nx + 0]).not.toBeNull(); // (0.5, 0.5) inside
    expect(g.lpDb[6 * g.nx + 7]).toBeNull(); // (7.5, 6.5) outside the notch
  });

  it("default cell is 1/80 of the shorter side within [0.1, 0.5] m", () => {
    const inp = inputOf(model([source(5, 5, 1.5, { 1000: 90 })], { 1000: 0.2 }));
    const g = estimateLpGrid(inp, 1.5, "A");
    expect(g.cellSizeM).toBeCloseTo(10 / 80, 9);
    expect(g.nx).toBe(80);
  });
});
