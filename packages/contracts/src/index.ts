/** Публичная версия схемы документа проекта (DAT-005 / API). */
export const SCHEMA_VERSION = "1.1" as const;
export type SchemaVersion = typeof SCHEMA_VERSION;

/** Префикс публичного HTTP API (API-001). */
export const API_V1_PREFIX = "/api/v1" as const;

/**
 * Черновой перечень путей API-001 (метод + path).
 * Полные request/response schemas появятся на STG-02+.
 */
export const API_V1_PATHS = [
  { method: "GET", path: "/api/v1/health" },
  { method: "GET", path: "/api/v1/capabilities" },
  { method: "GET", path: "/api/v1/projects" },
  { method: "POST", path: "/api/v1/projects" },
  { method: "GET", path: "/api/v1/projects/{id}/draft" },
  { method: "PATCH", path: "/api/v1/projects/{id}/draft" },
  { method: "POST", path: "/api/v1/projects/{id}/revisions" },
  { method: "POST", path: "/api/v1/revisions/{id}/validate" },
  { method: "POST", path: "/api/v1/jobs" },
  { method: "GET", path: "/api/v1/jobs/{id}" },
  { method: "GET", path: "/api/v1/jobs/{id}/events" },
  { method: "POST", path: "/api/v1/jobs/{id}/cancel" },
  { method: "GET", path: "/api/v1/results/{id}/manifest" },
  { method: "POST", path: "/api/v1/results/{id}/samples" },
  { method: "POST", path: "/api/v1/results/{id}/slices" },
  { method: "POST", path: "/api/v1/comparisons" },
  { method: "POST", path: "/api/v1/optimizations" },
  { method: "POST", path: "/api/v1/reports" },
  { method: "POST", path: "/api/v1/imports" },
  { method: "GET", path: "/api/v1/exports/{id}" },
] as const;
