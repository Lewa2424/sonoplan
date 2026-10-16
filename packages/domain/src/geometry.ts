import type { FloorVertex } from "./types.js";

const EPS = 1e-9;

export type ContourErrorCode =
  | "too_few_vertices"
  | "contour_not_closed"
  | "contour_self_intersection";

export interface ContourError {
  readonly code: ContourErrorCode;
  readonly message: string;
  readonly segmentIndexA?: number;
  readonly segmentIndexB?: number;
}

function nearlyEqual(a: number, b: number, eps = EPS): boolean {
  return Math.abs(a - b) <= eps;
}

function vertexEqual(a: FloorVertex, b: FloorVertex, eps = EPS): boolean {
  return nearlyEqual(a.x, b.x, eps) && nearlyEqual(a.y, b.y, eps);
}

/**
 * Нормализует контур: если первая и последняя вершины совпадают — убирает дубль.
 * Исходный массив не мутирует.
 */
export function stripClosingDuplicate(
  contour: readonly FloorVertex[],
): FloorVertex[] {
  if (contour.length >= 2) {
    const first = contour[0];
    const last = contour[contour.length - 1];
    if (first && last && vertexEqual(first, last)) {
      return contour.slice(0, -1);
    }
  }
  return [...contour];
}

/**
 * Контур считается явно замкнутым, если первая и последняя вершины совпадают
 * (в пределах EPS) и уникальных вершин ≥ 3.
 */
export function isContourExplicitlyClosed(
  contour: readonly FloorVertex[],
): boolean {
  if (contour.length < 4) {
    return false;
  }
  const first = contour[0];
  const last = contour[contour.length - 1];
  if (!first || !last || !vertexEqual(first, last)) {
    return false;
  }
  return stripClosingDuplicate(contour).length >= 3;
}

function cross(o: FloorVertex, a: FloorVertex, b: FloorVertex): number {
  return (a.x - o.x) * (b.y - o.y) - (a.y - o.y) * (b.x - o.x);
}

function onSegment(a: FloorVertex, b: FloorVertex, p: FloorVertex): boolean {
  return (
    Math.min(a.x, b.x) - EPS <= p.x &&
    p.x <= Math.max(a.x, b.x) + EPS &&
    Math.min(a.y, b.y) - EPS <= p.y &&
    p.y <= Math.max(a.y, b.y) + EPS
  );
}

/** Proper / improper intersection of segments AB and CD. */
function segmentsIntersect(
  a: FloorVertex,
  b: FloorVertex,
  c: FloorVertex,
  d: FloorVertex,
): boolean {
  const d1 = cross(a, b, c);
  const d2 = cross(a, b, d);
  const d3 = cross(c, d, a);
  const d4 = cross(c, d, b);

  if (
    ((d1 > EPS && d2 < -EPS) || (d1 < -EPS && d2 > EPS)) &&
    ((d3 > EPS && d4 < -EPS) || (d3 < -EPS && d4 > EPS))
  ) {
    return true;
  }

  if (Math.abs(d1) <= EPS && onSegment(a, b, c)) return true;
  if (Math.abs(d2) <= EPS && onSegment(a, b, d)) return true;
  if (Math.abs(d3) <= EPS && onSegment(c, d, a)) return true;
  if (Math.abs(d4) <= EPS && onSegment(c, d, b)) return true;
  return false;
}

/**
 * Самопересечение замкнутого многоугольника (блокирующая ошибка).
 * Смежные рёбра не считаются пересечением.
 */
export function findSelfIntersections(
  contour: readonly FloorVertex[],
): ContourError[] {
  const ring = stripClosingDuplicate(contour);
  const n = ring.length;
  if (n < 3) {
    return [];
  }

  const errors: ContourError[] = [];
  for (let i = 0; i < n; i++) {
    const a = ring[i]!;
    const b = ring[(i + 1) % n]!;
    for (let j = i + 1; j < n; j++) {
      const adjacent =
        j === i ||
        (j + 1) % n === i ||
        i + 1 === j ||
        (i === 0 && j === n - 1);
      if (adjacent) {
        continue;
      }
      const c = ring[j]!;
      const d = ring[(j + 1) % n]!;
      if (segmentsIntersect(a, b, c, d)) {
        errors.push({
          code: "contour_self_intersection",
          message: `Floor contour self-intersects at edges ${i} and ${j}`,
          segmentIndexA: i,
          segmentIndexB: j,
        });
      }
    }
  }
  return errors;
}

/**
 * Проверка контура комнаты: замкнутость и отсутствие самопересечений.
 */
export function validateFloorContour(
  contour: readonly FloorVertex[],
): ContourError[] {
  const errors: ContourError[] = [];
  const unique = stripClosingDuplicate(contour);

  if (unique.length < 3) {
    errors.push({
      code: "too_few_vertices",
      message: "Floor contour needs at least 3 distinct vertices",
    });
    return errors;
  }

  if (!isContourExplicitlyClosed(contour)) {
    errors.push({
      code: "contour_not_closed",
      message:
        "Floor contour must be explicitly closed (first vertex equals last)",
    });
  }

  errors.push(...findSelfIntersections(contour));
  return errors;
}

/** Point-in-polygon (ray casting) в плоскости пола XY. */
export function pointInPolygon(
  point: FloorVertex,
  contour: readonly FloorVertex[],
): boolean {
  const ring = stripClosingDuplicate(contour);
  const n = ring.length;
  if (n < 3) {
    return false;
  }

  let inside = false;
  for (let i = 0, j = n - 1; i < n; j = i++) {
    const yi = ring[i]!.y;
    const yj = ring[j]!.y;
    const xi = ring[i]!.x;
    const xj = ring[j]!.x;
    const denom = yj - yi === 0 ? EPS : yj - yi;
    if (
      yi > point.y !== yj > point.y &&
      point.x < ((xj - xi) * (point.y - yi)) / denom + xi
    ) {
      inside = !inside;
    }
  }
  return inside;
}
