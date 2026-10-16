import { apiFetch } from "./client";
import type { JobCreate, JobResponse } from "./types";

export async function createJob(
  body: JobCreate,
  idempotencyKey: string,
): Promise<JobResponse> {
  const { data } = await apiFetch<JobResponse>("/api/v1/jobs", {
    method: "POST",
    headers: { "Idempotency-Key": idempotencyKey },
    body: JSON.stringify(body),
  });
  return data;
}

export async function getJob(jobId: string): Promise<JobResponse> {
  const { data } = await apiFetch<JobResponse>(`/api/v1/jobs/${jobId}`);
  return data;
}

export async function cancelJob(jobId: string): Promise<JobResponse> {
  const { data } = await apiFetch<JobResponse>(`/api/v1/jobs/${jobId}/cancel`, {
    method: "POST",
  });
  return data;
}

export function newIdempotencyKey(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return `web-${crypto.randomUUID()}`;
  }
  return `web-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}
