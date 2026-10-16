import { describe, expect, it } from "vitest";
import {
  findSelfIntersections,
  isContourExplicitlyClosed,
  pointInPolygon,
  validateFloorContour,
} from "./geometry.js";

/** Прямоугольная комната 10×6 м, явно замкнутая. */
const RECT_CLOSED = [
  { x: 0, y: 0 },
  { x: 10, y: 0 },
  { x: 10, y: 6 },
  { x: 0, y: 6 },
  { x: 0, y: 0 },
];

/** Простая неправильная (L-образная) комната. */
const L_SHAPE_CLOSED = [
  { x: 0, y: 0 },
  { x: 8, y: 0 },
  { x: 8, y: 3 },
  { x: 3, y: 3 },
  { x: 3, y: 7 },
  { x: 0, y: 7 },
  { x: 0, y: 0 },
];

/** Самопересекающийся «бантик». */
const BOWTIE = [
  { x: 0, y: 0 },
  { x: 4, y: 4 },
  { x: 4, y: 0 },
  { x: 0, y: 4 },
  { x: 0, y: 0 },
];

describe("floor contour", () => {
  it("accepts closed rectangle", () => {
    expect(isContourExplicitlyClosed(RECT_CLOSED)).toBe(true);
    expect(validateFloorContour(RECT_CLOSED)).toEqual([]);
  });

  it("accepts closed irregular L-shape", () => {
    expect(validateFloorContour(L_SHAPE_CLOSED)).toEqual([]);
  });

  it("rejects open contour as blocking", () => {
    const open = RECT_CLOSED.slice(0, -1);
    const errors = validateFloorContour(open);
    expect(errors.some((e) => e.code === "contour_not_closed")).toBe(true);
  });

  it("rejects self-intersection as blocking", () => {
    const errors = findSelfIntersections(BOWTIE);
    expect(errors.length).toBeGreaterThan(0);
    expect(errors[0]?.code).toBe("contour_self_intersection");
    expect(
      validateFloorContour(BOWTIE).some((e) => e.code === "contour_self_intersection"),
    ).toBe(true);
  });

  it("point-in-polygon for rectangle", () => {
    expect(pointInPolygon({ x: 5, y: 3 }, RECT_CLOSED)).toBe(true);
    expect(pointInPolygon({ x: -1, y: 3 }, RECT_CLOSED)).toBe(false);
  });
});
