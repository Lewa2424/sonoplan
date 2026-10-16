import type { FloorVertex } from "@sonoplan/domain";
import { stripClosingDuplicate } from "@sonoplan/domain";

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
