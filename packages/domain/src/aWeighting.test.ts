import { describe, expect, it } from "vitest";
import { aWeightingDb } from "./aWeighting.js";

describe("aWeightingDb (IEC 61672-1)", () => {
  it("returns tabulated octave corrections", () => {
    expect(aWeightingDb(63)).toBe(-26.2);
    expect(aWeightingDb(125)).toBe(-16.1);
    expect(aWeightingDb(1000)).toBe(0);
    expect(aWeightingDb(4000)).toBe(1.0);
    expect(aWeightingDb(8000)).toBe(-1.1);
  });

  it("returns null for a non-nominal band", () => {
    expect(aWeightingDb(1100)).toBeNull();
  });
});
