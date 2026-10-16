/** Публичный базовый URL API. По умолчанию — локальный FastAPI STG-02. */
export const API_BASE_URL: string =
  import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, "") ||
  "http://127.0.0.1:8000";
