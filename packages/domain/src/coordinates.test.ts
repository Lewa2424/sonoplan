import { describe, expect, it } from "vitest";
import { projectToThree, threeToProject } from "./coordinates.js";
import { finiteOrNull, unknownQuantity } from "./units.js";

describe("projectToThree / threeToProject", () => {
  it("maps (X, Y, Z) → (X, Z, −Y)", () => {
    expect(projectToThree({ x: 2, y: 3, z: 4 })).toEqual({
      x: 2,
      y: 4,
      z: -3,
    });
  });

  it("round-trips project → three → project", () => {
    const p = { x: 1.5, y: -2, z: 0.75 };
    expect(threeToProject(projectToThree(p))).toEqual(p);
  });

  it("round-trips three → project → three", () => {
    const t = { x: 10, y: 1.2, z: -4 };
    expect(projectToThree(threeToProject(t))).toEqual(t);
  });
});

describe("null ≠ 0", () => {
  it("keeps unknown as null with reason", () => {
    const q = unknownQuantity("m", "not_measured");
    expect(q.value).toBeNull();
    expect(q.nullReason).toBe("not_measured");
    expect(q.value).not.toBe(0);
  });

  it("rejects non-finite as null, not zero", () => {
    expect(finiteOrNull(Number.NaN)).toEqual({
      value: null,
      nullReason: "non_finite",
    });
    expect(finiteOrNull(Number.POSITIVE_INFINITY).value).toBeNull();
  });
});
