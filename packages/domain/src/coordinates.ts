/**
 * Система координат проекта (GEO):
 * - X, Y — плоскость пола
 * - Z — вверх
 *
 * Three.js (правая рука, Y вверх сцены):
 * - project (X, Y, Z) → three (X, Z, −Y)
 * Обратное преобразование одной функцией пары.
 */

export interface ProjectPoint3 {
  readonly x: number;
  readonly y: number;
  readonly z: number;
}

export interface ThreePoint3 {
  readonly x: number;
  readonly y: number;
  readonly z: number;
}

/** Проект → Three.js: (X, Y, Z) → (X, Z, −Y). */
export function projectToThree(p: ProjectPoint3): ThreePoint3 {
  return { x: p.x, y: p.z, z: -p.y };
}

/** Three.js → проект: (X, Y, Z) → (X, −Z, Y). */
export function threeToProject(t: ThreePoint3): ProjectPoint3 {
  return { x: t.x, y: -t.z, z: t.y };
}
