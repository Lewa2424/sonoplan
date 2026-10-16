import { describe, expect, it } from "vitest";
import {
  isContourExplicitlyClosed,
  validateFloorContour,
} from "@sonoplan/domain";
import {
  contourVertexAngles,
  ensureClosedContour,
  lShapeContour,
  projectToRightAngle,
  rectangleContour,
  smallerAngleDeg,
  snapNearAxisAlignedEdges,
  snapNearRightAngles,
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

  it("rectangle angles are all 90°", () => {
    const angles = contourVertexAngles(rectangleContour(10, 6));
    expect(angles).toHaveLength(4);
    for (const a of angles) {
      expect(a.degrees).toBeCloseTo(90, 5);
      expect(a.nearRightAngle).toBe(true);
    }
  });

  it("projectToRightAngle yields 90° at B", () => {
    const a = { x: 0, y: 0 };
    const b = { x: 3, y: 0.2 };
    const c = { x: 3.1, y: 4 };
    const b2 = projectToRightAngle(a, b, c);
    const abx = a.x - b2.x;
    const aby = a.y - b2.y;
    const cbx = c.x - b2.x;
    const cby = c.y - b2.y;
    const dot = abx * cbx + aby * cby;
    expect(Math.abs(dot)).toBeLessThan(1e-6);
  });

  it("smallerAngleDeg maps reflex to ≤180", () => {
    expect(smallerAngleDeg(260)).toBeCloseTo(100, 5);
    expect(smallerAngleDeg(90)).toBeCloseTo(90, 5);
    expect(smallerAngleDeg(270)).toBeCloseTo(90, 5);
  });

  it("snapNearRightAngles fixes 90±5 corners", () => {
    const crooked = ensureClosedContour([
      { x: 0, y: 0 },
      { x: 10, y: 0 },
      { x: 10.3, y: 6 },
      { x: 0, y: 6 },
    ]);
    const before = contourVertexAngles(crooked);
    expect(
      before.some((a) => a.nearRightAngle && Math.abs(a.degrees - 90) > 0.05),
    ).toBe(true);
    const snapped = snapNearRightAngles(crooked);
    const after = contourVertexAngles(snapped);
    for (const a of after) {
      if (before[a.index]?.nearRightAngle) {
        expect(Math.abs(a.degrees - 90)).toBeLessThan(0.5);
      }
    }
    expect(validateFloorContour(snapped)).toEqual([]);
  });

  it("snapNearAxisAlignedEdges straightens near-horizontal wall", () => {
    const crooked = ensureClosedContour([
      { x: 0, y: 0 },
      { x: 10, y: 0.2 },
      { x: 10, y: 6 },
      { x: 0, y: 6 },
    ]);
    const snapped = snapNearAxisAlignedEdges(crooked);
    const pts = snapped.slice(0, -1);
    expect(Math.abs(pts[0]!.y - pts[1]!.y)).toBeLessThan(1e-6);
    expect(validateFloorContour(snapped)).toEqual([]);
  });
});
