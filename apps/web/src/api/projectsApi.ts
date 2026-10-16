import type { ProjectDraft } from "@sonoplan/domain";
import { apiFetch } from "./client";
import type {
  DraftResponse,
  ProjectListResponse,
  ProjectSummary,
  RevisionCreated,
  ValidateResponse,
} from "./types";

export async function listProjects(): Promise<readonly ProjectSummary[]> {
  const { data } = await apiFetch<ProjectListResponse>("/api/v1/projects");
  return data.items;
}

export async function createProject(name: string): Promise<ProjectSummary> {
  const { data } = await apiFetch<ProjectSummary>("/api/v1/projects", {
    method: "POST",
    body: JSON.stringify({ name }),
  });
  return data;
}

export async function getDraft(
  projectId: string,
): Promise<{ draft: DraftResponse; etag: string }> {
  const { data, etag } = await apiFetch<DraftResponse>(
    `/api/v1/projects/${projectId}/draft`,
  );
  const resolved = etag ?? data.etag;
  if (!resolved) {
    throw new Error("Draft response missing ETag");
  }
  return { draft: data, etag: resolved };
}

export async function patchDraft(
  projectId: string,
  etag: string,
  body: Partial<ProjectDraft> & { model?: ProjectDraft["model"] },
): Promise<{ draft: DraftResponse; etag: string }> {
  const { data, etag: next } = await apiFetch<DraftResponse>(
    `/api/v1/projects/${projectId}/draft`,
    {
      method: "PATCH",
      headers: { "If-Match": `"${etag}"` },
      body: JSON.stringify(body),
    },
  );
  const resolved = next ?? data.etag;
  if (!resolved) {
    throw new Error("PATCH draft response missing ETag");
  }
  return { draft: data, etag: resolved };
}

export async function createRevision(
  projectId: string,
): Promise<RevisionCreated> {
  const { data } = await apiFetch<RevisionCreated>(
    `/api/v1/projects/${projectId}/revisions`,
    {
      method: "POST",
      body: JSON.stringify({}),
    },
  );
  return data;
}

export async function validateRevision(
  revisionId: string,
): Promise<ValidateResponse> {
  const { data } = await apiFetch<ValidateResponse>(
    `/api/v1/revisions/${revisionId}/validate`,
    { method: "POST" },
  );
  return data;
}

export async function checkApiHealth(): Promise<boolean> {
  try {
    await apiFetch<{ status: string }>("/api/v1/health");
    return true;
  } catch {
    return false;
  }
}
