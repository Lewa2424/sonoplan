import { API_BASE_URL } from "./config";

export class ApiError extends Error {
  readonly status: number;
  readonly detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

export class NetworkError extends Error {
  constructor(cause?: unknown) {
    super(
      cause instanceof Error
        ? `Нет связи с API (${API_BASE_URL}): ${cause.message}`
        : `Нет связи с API (${API_BASE_URL})`,
    );
    this.name = "NetworkError";
  }
}

function parseDetail(data: unknown): string {
  if (data && typeof data === "object" && "detail" in data) {
    const detail = (data as { detail: unknown }).detail;
    if (typeof detail === "string") {
      return detail;
    }
    if (Array.isArray(detail)) {
      return detail.map((d) => JSON.stringify(d)).join("; ");
    }
  }
  return "Ошибка API";
}

export async function apiFetch<T>(
  path: string,
  init: RequestInit = {},
): Promise<{ data: T; etag: string | null }> {
  const url = `${API_BASE_URL}${path.startsWith("/") ? path : `/${path}`}`;
  let response: Response;
  try {
    response = await fetch(url, {
      ...init,
      headers: {
        Accept: "application/json",
        ...(init.body ? { "Content-Type": "application/json" } : {}),
        ...init.headers,
      },
    });
  } catch (cause) {
    throw new NetworkError(cause);
  }

  const etagRaw = response.headers.get("ETag");
  const etag = etagRaw ? etagRaw.replace(/^"|"$/g, "") : null;

  if (response.status === 204) {
    return { data: undefined as T, etag };
  }

  let body: unknown = null;
  const text = await response.text();
  if (text) {
    try {
      body = JSON.parse(text) as unknown;
    } catch {
      body = text;
    }
  }

  if (!response.ok) {
    const detail =
      typeof body === "string" && body.length > 0
        ? body
        : parseDetail(body);
    throw new ApiError(response.status, detail);
  }

  return { data: body as T, etag };
}
