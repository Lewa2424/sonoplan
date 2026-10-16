import type { FloorVertex } from "@sonoplan/domain";
import { stripClosingDuplicate } from "@sonoplan/domain";

/** Tolerance: |smallerAngle − 90°| ≤ this → snap to exact 90° (Thales). */
export const RIGHT_ANGLE_SNAP_TOLERANCE_DEG = 5;

export interface ContourVertexAngle {
  readonly index: number;
  /**
   * Smaller corner angle at vertex, degrees (0…180).
   * e.g. interior 260° → displayed/used as 100°.
   */
  readonly degrees: number;
  /** True if within snap tolerance of 90°. */
  readonly nearRightAngle: boolean;
}

/** min(θ, 360−θ) so UI never shows reflex corners as &gt;180°. */
export function smallerAngleDeg(degrees: number): number {
  let d = degrees % 360;
  if (d < 0) d += 360;
  return Math.min(d, 360 - d);
}

/**
 * Прямоугольник в плоскости пола (м), явно замкнутый (первая === последняя).
 * origin — нижний-левый угол в координатах проекта (X,Y).
 */
export function rectangleContour(
  widthM: number,
  depthM: number,
  originX = 0,
  originY = 0,
): FloorVertex[] {
  if (!(widthM > 0) || !(depthM > 0)) {
    throw new Error("rectangleContour: width and depth must be > 0");
  }
  const x0 = originX;
  const y0 = originY;
  const x1 = originX + widthM;
  const y1 = originY + depthM;
  return [
    { x: x0, y: y0 },
    { x: x1, y: y0 },
    { x: x1, y: y1 },
    { x: x0, y: y1 },
    { x: x0, y: y0 },
  ];
}

/**
 * L-образный контур: внешний прямоугольник width×depth с вырезом
 * из правого дальнего угла (cutWidth × cutDepth).
 */
export function lShapeContour(
  widthM: number,
  depthM: number,
  cutWidthM: number,
  cutDepthM: number,
  originX = 0,
  originY = 0,
): FloorVertex[] {
  if (
    !(widthM > 0) ||
    !(depthM > 0) ||
    !(cutWidthM > 0) ||
    !(cutDepthM > 0) ||
    cutWidthM >= widthM ||
    cutDepthM >= depthM
  ) {
    throw new Error("lShapeContour: invalid dimensions");
  }
  const x0 = originX;
  const y0 = originY;
  const x1 = originX + widthM;
  const y1 = originY + depthM;
  const xc = x1 - cutWidthM;
  const yc = y1 - cutDepthM;
  return [
    { x: x0, y: y0 },
    { x: x1, y: y0 },
    { x: x1, y: yc },
    { x: xc, y: yc },
    { x: xc, y: y1 },
    { x: x0, y: y1 },
    { x: x0, y: y0 },
  ];
}

/** Добавляет замыкающую вершину, если контур ещё не замкнут явно. */
export function ensureClosedContour(
  contour: readonly FloorVertex[],
): FloorVertex[] {
  const unique = stripClosingDuplicate(contour);
  if (unique.length < 3) {
    throw new Error("ensureClosedContour: need ≥3 unique vertices");
  }
  const first = unique[0];
  if (!first) {
    throw new Error("ensureClosedContour: empty contour");
  }
  return [...unique, { x: first.x, y: first.y }];
}

/** Плоский массив [x,y,x,y,…] для Konva.Line (координаты проекта → stage уже смасштабированы снаружи). */
export function contourToFlatPoints(
  contour: readonly FloorVertex[],
  scale: number,
  offsetX: number,
  offsetY: number,
): number[] {
  const out: number[] = [];
  for (const v of contour) {
    out.push(offsetX + v.x * scale, offsetY - v.y * scale);
  }
  return out;
}

/** Bounding box уникальных вершин (без замыкающего дубля). */
export function contourBounds(contour: readonly FloorVertex[]): {
  minX: number;
  minY: number;
  maxX: number;
  maxY: number;
  width: number;
  depth: number;
} {
  const pts = stripClosingDuplicate(contour);
  if (pts.length === 0) {
    return { minX: 0, minY: 0, maxX: 0, maxY: 0, width: 0, depth: 0 };
  }
  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;
  for (const p of pts) {
    minX = Math.min(minX, p.x);
    minY = Math.min(minY, p.y);
    maxX = Math.max(maxX, p.x);
    maxY = Math.max(maxY, p.y);
  }
  return {
    minX,
    minY,
    maxX,
    maxY,
    width: maxX - minX,
    depth: maxY - minY,
  };
}

function signedArea2(pts: readonly FloorVertex[]): number {
  let a = 0;
  for (let i = 0; i < pts.length; i++) {
    const p = pts[i]!;
    const q = pts[(i + 1) % pts.length]!;
    a += p.x * q.y - q.x * p.y;
  }
  return a;
}

function interiorAngleDeg(
  prev: FloorVertex,
  curr: FloorVertex,
  next: FloorVertex,
  ccw: boolean,
): number {
  const e1x = curr.x - prev.x;
  const e1y = curr.y - prev.y;
  const e2x = next.x - curr.x;
  const e2y = next.y - curr.y;
  const cross = e1x * e2y - e1y * e2x;
  const dot = e1x * e2x + e1y * e2y;
  const turn = Math.atan2(cross, dot);
  let interior = ccw ? Math.PI - turn : Math.PI + turn;
  while (interior < 0) interior += 2 * Math.PI;
  while (interior >= 2 * Math.PI) interior -= 2 * Math.PI;
  return (interior * 180) / Math.PI;
}

/** Corner angles at each unique vertex (smaller ≤180°, including exact 90°). */
export function contourVertexAngles(
  contour: readonly FloorVertex[],
  toleranceDeg: number = RIGHT_ANGLE_SNAP_TOLERANCE_DEG,
): ContourVertexAngle[] {
  const pts = stripClosingDuplicate(contour);
  if (pts.length < 3) return [];
  const ccw = signedArea2(pts) > 0;
  const out: ContourVertexAngle[] = [];
  for (let i = 0; i < pts.length; i++) {
    const prev = pts[(i - 1 + pts.length) % pts.length]!;
    const curr = pts[i]!;
    const next = pts[(i + 1) % pts.length]!;
    const degrees = smallerAngleDeg(interiorAngleDeg(prev, curr, next, ccw));
    out.push({
      index: i,
      degrees,
      nearRightAngle: Math.abs(degrees - 90) <= toleranceDeg,
    });
  }
  return out;
}

/**
 * Smaller corner angle for an open polyline at `cornerIndex`
 * (used while dragging the last draft segment).
 */
export function openPolylineCornerAngleDeg(
  pts: readonly FloorVertex[],
  cornerIndex: number,
): number | null {
  if (pts.length < 3) return null;
  if (cornerIndex <= 0 || cornerIndex >= pts.length - 1) return null;
  const prev = pts[cornerIndex - 1]!;
  const curr = pts[cornerIndex]!;
  const next = pts[cornerIndex + 1]!;
  // Local orientation from the three points only.
  const e1x = curr.x - prev.x;
  const e1y = curr.y - prev.y;
  const e2x = next.x - curr.x;
  const e2y = next.y - curr.y;
  const cross = e1x * e2y - e1y * e2x;
  const dot = e1x * e2x + e1y * e2y;
  const turn = Math.atan2(cross, dot);
  const interior = Math.PI - turn;
  let deg = (interior * 180) / Math.PI;
  while (deg < 0) deg += 360;
  while (deg >= 360) deg -= 360;
  return smallerAngleDeg(deg);
}

/**
 * Move vertex B onto the Thales circle with diameter AC so ∠ABC = 90°.
 * Keeps side of line AC (same half-plane as original B).
 */
export function projectToRightAngle(
  a: FloorVertex,
  b: FloorVertex,
  c: FloorVertex,
): FloorVertex {
  const mx = (a.x + c.x) / 2;
  const my = (a.y + c.y) / 2;
  const acx = c.x - a.x;
  const acy = c.y - a.y;
  const r = Math.hypot(acx, acy) / 2;
  if (!(r > 1e-9)) return { x: b.x, y: b.y };

  let dx = b.x - mx;
  let dy = b.y - my;
  let len = Math.hypot(dx, dy);
  if (!(len > 1e-9)) {
    dx = -acy;
    dy = acx;
    len = Math.hypot(dx, dy);
    if (!(len > 1e-9)) return { x: b.x, y: b.y };
  }
  const scale = r / len;
  return { x: mx + dx * scale, y: my + dy * scale };
}

/**
 * Edges within tolDeg of horizontal/vertical become exactly axis-aligned
 * (moves the edge end vertex). Makes «Выровнять» visible on walls.
 */
export function snapNearAxisAlignedEdges(
  contour: readonly FloorVertex[],
  toleranceDeg: number = RIGHT_ANGLE_SNAP_TOLERANCE_DEG,
): FloorVertex[] {
  let pts = stripClosingDuplicate(contour).map((p) => ({ x: p.x, y: p.y }));
  if (pts.length < 2) {
    return ensureClosedContour(contour);
  }
  const n = pts.length;
  const maxPasses = n * 3;
  for (let pass = 0; pass < maxPasses; pass++) {
    let moved = false;
    for (let i = 0; i < n; i++) {
      const a = pts[i]!;
      const b = pts[(i + 1) % n]!;
      const dx = b.x - a.x;
      const dy = b.y - a.y;
      const len = Math.hypot(dx, dy);
      if (!(len > 1e-9)) continue;
      const deg = (Math.atan2(dy, dx) * 180) / Math.PI;
      const norm = ((deg % 180) + 180) % 180; // 0…180
      const distH = Math.min(norm, 180 - norm);
      const distV = Math.abs(norm - 90);
      if (distH <= toleranceDeg && distH <= distV) {
        if (Math.abs(b.y - a.y) > 1e-9) {
          pts[(i + 1) % n] = { x: b.x, y: a.y };
          moved = true;
        }
      } else if (distV <= toleranceDeg) {
        if (Math.abs(b.x - a.x) > 1e-9) {
          pts[(i + 1) % n] = { x: a.x, y: b.y };
          moved = true;
        }
      }
    }
    if (!moved) break;
  }
  return ensureClosedContour(pts);
}

/**
 * Vertices with interior angle in 90±tol are moved to exact 90° (Thales).
 * One worst vertex per pass so neighbors do not fight. Returns closed contour.
 */
export function snapNearRightAngles(
  contour: readonly FloorVertex[],
  toleranceDeg: number = RIGHT_ANGLE_SNAP_TOLERANCE_DEG,
): FloorVertex[] {
  // First straighten near-axis walls, then lock near-right corners.
  let pts = stripClosingDuplicate(
    snapNearAxisAlignedEdges(contour, toleranceDeg),
  ).map((p) => ({ x: p.x, y: p.y }));
  if (pts.length < 3) {
    return ensureClosedContour(contour);
  }
  const settled = 0.05;
  const maxPasses = pts.length * 6;
  for (let pass = 0; pass < maxPasses; pass++) {
    const angles = contourVertexAngles(pts, toleranceDeg);
    let worst: ContourVertexAngle | null = null;
    let worstDev = 0;
    for (const ang of angles) {
      if (!ang.nearRightAngle) continue;
      const dev = Math.abs(ang.degrees - 90);
      if (dev <= settled) continue;
      if (dev > worstDev) {
        worstDev = dev;
        worst = ang;
      }
    }
    if (!worst) break;
    const i = worst.index;
    const a = pts[(i - 1 + pts.length) % pts.length]!;
    const b = pts[i]!;
    const c = pts[(i + 1) % pts.length]!;
    pts = pts.map((p, idx) => (idx === i ? projectToRightAngle(a, b, c) : p));
  }
  // Second axis pass after corner snaps.
  return snapNearAxisAlignedEdges(ensureClosedContour(pts), toleranceDeg);
}

/** Max distance (m) to first vertex to auto-close polygon draft. */
export const POLYGON_CLOSE_SNAP_M = 0.5;

/** Format for UI: one decimal if needed, else integer. */
export function formatAngleDeg(degrees: number): string {
  const rounded = Math.round(degrees * 10) / 10;
  if (Math.abs(rounded - Math.round(rounded)) < 0.05) {
    return `${Math.round(rounded)}°`;
  }
  return `${rounded.toFixed(1)}°`;
}

/** Integer degrees for live drag feedback. */
export function formatAngleDegInt(degrees: number): string {
  return `${Math.round(degrees)}°`;
}

/**
 * Inward offset (project metres) from vertex toward polygon interior,
 * for placing angle labels inside the perimeter.
 */
export function inwardLabelOffsetM(
  prev: FloorVertex,
  curr: FloorVertex,
  next: FloorVertex,
  ccw: boolean,
  insetM: number,
): FloorVertex {
  const e1x = curr.x - prev.x;
  const e1y = curr.y - prev.y;
  const e2x = next.x - curr.x;
  const e2y = next.y - curr.y;
  let n1x = -e1y;
  let n1y = e1x;
  let n2x = -e2y;
  let n2y = e2x;
  if (!ccw) {
    n1x = -n1x;
    n1y = -n1y;
    n2x = -n2x;
    n2y = -n2y;
  }
  const l1 = Math.hypot(n1x, n1y) || 1;
  const l2 = Math.hypot(n2x, n2y) || 1;
  let bx = n1x / l1 + n2x / l2;
  let by = n1y / l1 + n2y / l2;
  let bl = Math.hypot(bx, by);
  if (bl < 1e-9) {
    bx = n1x / l1;
    by = n1y / l1;
    bl = 1;
  }
  bx /= bl;
  by /= bl;
  return { x: curr.x + bx * insetM, y: curr.y + by * insetM };
}

export function contourWindingCcw(contour: readonly FloorVertex[]): boolean {
  return signedArea2(stripClosingDuplicate(contour)) > 0;
}

/**
 * Screen-space label anchors inside the polygon; lightly separates pairs
 * that would otherwise overlap.
 */
export function contourAngleLabelPositions(
  contour: readonly FloorVertex[],
  scale: number,
  offsetX: number,
  offsetY: number,
  insetPx = 18,
  minSepPx = 22,
): { x: number; y: number }[] {
  const pts = stripClosingDuplicate(contour);
  if (pts.length === 0) return [];
  const ccw = signedArea2(pts) > 0;
  const insetM = insetPx / Math.max(scale, 1e-6);
  const positions = pts.map((curr, i) => {
    const prev = pts[(i - 1 + pts.length) % pts.length]!;
    const next = pts[(i + 1) % pts.length]!;
    const p = inwardLabelOffsetM(prev, curr, next, ccw, insetM);
    return {
      x: offsetX + p.x * scale,
      y: offsetY - p.y * scale,
    };
  });
  // Separate overlapping labels (2 passes).
  for (let pass = 0; pass < 2; pass++) {
    for (let i = 0; i < positions.length; i++) {
      for (let j = i + 1; j < positions.length; j++) {
        const a = positions[i]!;
        const b = positions[j]!;
        const dx = b.x - a.x;
        const dy = b.y - a.y;
        const dist = Math.hypot(dx, dy);
        if (dist >= minSepPx || dist < 1e-6) continue;
        const push = (minSepPx - dist) / 2;
        const ux = dx / dist;
        const uy = dy / dist;
        a.x -= ux * push;
        a.y -= uy * push;
        b.x += ux * push;
        b.y += uy * push;
      }
    }
  }
  return positions;
}
