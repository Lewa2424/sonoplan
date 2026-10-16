import { describe, expect, it } from "vitest";
import {
  isContourExplicitlyClosed,
  validateFloorContour,
} from "@sonoplan/domain";
import {
  ensureClosedContour,
  lShapeContour,
  rectangleContour,
} from "./contourHelpers";

describe("contourHelpers", () => {
  it("rectangleContour is explicitly closed and valid", () => {
    const c = rectangleContour(20, 12);
    expect(isContourExplicitlyClosed(c)).toBe(true);
    expect(validateFloorContour(c)).toEqual([]);
    expect(c).toHaveLength(5);
  });

  it("lShapeContour is closed, non-self-intersecting", () => {
    const c = lShapeContour(20, 15, 8, 6);
    expect(isContourExplicitlyClosed(c)).toBe(true);
    expect(validateFloorContour(c)).toEqual([]);
  });

  it("ensureClosedContour closes open polygon", () => {
    const open = [
      { x: 0, y: 0 },
      { x: 10, y: 0 },
      { x: 10, y: 8 },
      { x: 0, y: 8 },
    ];
    const closed = ensureClosedContour(open);
    expect(isContourExplicitlyClosed(closed)).toBe(true);
    expect(validateFloorContour(closed)).toEqual([]);
  });
});
