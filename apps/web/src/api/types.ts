import type { ProjectDraft } from "@sonoplan/domain";

export interface ProjectSummary {
  readonly id: string;
  readonly ownerId: string;
  readonly name: string;
  readonly accessPolicy: string;
  readonly schemaVersion: string;
  readonly currentRevisionId: string | null;
}

export interface ProjectListResponse {
  readonly items: readonly ProjectSummary[];
}

export interface DraftResponse {
  readonly projectId: string;
  readonly etag: string;
  readonly body: ProjectDraft;
}

export interface RevisionCreated {
  readonly revisionId: string;
  readonly snapshotHash: string;
  readonly schemaVersion: string;
  readonly projectId: string;
  readonly parentId: string | null;
}

export interface ApiValidationIssue {
  readonly code: string;
  readonly severity: string;
  readonly message: string;
  readonly path?: string | null;
  readonly entityId?: string | null;
}

export interface ValidateResponse {
  readonly revisionId: string;
  readonly snapshotHash: string;
  readonly ok: boolean;
  readonly errors: readonly ApiValidationIssue[];
  readonly warnings: readonly ApiValidationIssue[];
}
