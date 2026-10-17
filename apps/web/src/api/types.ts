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

export type JobStatus =
  | "created"
  | "queued"
  | "running"
  | "completed"
  | "failed"
  | "cancelled";

export interface JobCreate {
  readonly revisionId: string;
  readonly snapshotHash?: string;
}

export interface PunctualReceiverSummary {
  readonly receiverId?: string;
  readonly relativePath?: string;
  readonly energySumGlobal?: number;
  readonly lpDbGlobal?: number | null;
  readonly lpDbGlobalReason?: string | null;
  /** A-взвешенный суммарный уровень (дБА); нет у заданий до A-коррекции. */
  readonly laDbGlobal?: number | null;
  readonly laDbGlobalReason?: string | null;
  readonly bandLabels?: readonly string[];
  readonly bands?: readonly {
    readonly label?: string;
    readonly energySum?: number;
    readonly lpDb?: number | null;
  }[];
}

/** Сетка сечения SPPS; origin — в координатах SPPS (проект − exportMeta.origin). */
export interface ResultGridStub {
  readonly originX?: number;
  readonly originY?: number;
  readonly cellSizeM?: number;
  readonly cellSizeYM?: number;
  readonly nx?: number;
  readonly ny?: number;
  readonly zM?: number;
  /** Невзвешенный Lp, дБ. */
  readonly lpDb?: readonly (number | null)[];
  /** A-взвешенный Lp, дБА. */
  readonly laDb?: readonly (number | null)[];
  readonly laBandsHz?: readonly number[];
}

export interface ExportMetaStub {
  readonly mode?: string;
  readonly originX?: number;
  readonly originY?: number;
  readonly coupeZM?: number | null;
}

export interface ResultManifestStub {
  readonly schemaVersion?: string;
  readonly grid?: ResultGridStub | null;
  readonly exportMeta?: ExportMetaStub;
  readonly jobId?: string;
  readonly revisionId?: string;
  readonly snapshotHash?: string;
  readonly quantity?: string | null;
  readonly unit?: string | null;
  readonly displayQuantity?: string | null;
  readonly displayUnit?: string | null;
  readonly artifactPaths?: readonly string[];
  readonly mapAvailable?: boolean;
  readonly mapDeferredReason?: string | null;
  readonly punctualReceivers?: readonly PunctualReceiverSummary[];
  readonly executionMode?: string | null;
  readonly notes?: readonly string[];
  readonly attempt?: {
    readonly ok?: boolean;
    readonly error_code?: string | null;
    readonly error_message?: string | null;
    readonly artifact_paths?: readonly string[];
  };
}

export interface JobResponse {
  readonly id: string;
  readonly projectId: string;
  readonly revisionId: string;
  readonly snapshotHash: string;
  readonly status: JobStatus | string;
  readonly errorCode: string | null;
  readonly errorMessage: string | null;
  readonly resultManifest: ResultManifestStub | null;
  readonly cancelRequested: boolean;
  readonly createdAt: string;
  readonly updatedAt: string;
  readonly startedAt: string | null;
  readonly finishedAt: string | null;
}
