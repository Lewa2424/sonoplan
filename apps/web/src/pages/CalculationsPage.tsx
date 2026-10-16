import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, NetworkError } from "../api/client";
import { cancelJob, createJob, getJob, newIdempotencyKey } from "../api/jobsApi";
import type { JobResponse } from "../api/types";
import { ru } from "../i18n/ru";
import { useEditorStore } from "../store/editorStore";

const TERMINAL = new Set(["completed", "failed", "cancelled"]);
const POLL_MS = 1500;

export function CalculationsPage() {
  const lastRevision = useEditorStore((s) => s.lastRevision);
  const connectionMode = useEditorStore((s) => s.connectionMode);

  const [job, setJob] = useState<JobResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pollRef = useRef<number | null>(null);

  const stopPoll = useCallback(() => {
    if (pollRef.current !== null) {
      window.clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  useEffect(() => () => stopPoll(), [stopPoll]);

  const refreshJob = useCallback(
    async (jobId: string) => {
      try {
        const next = await getJob(jobId);
        setJob(next);
        if (TERMINAL.has(next.status)) {
          stopPoll();
        }
      } catch (err) {
        stopPoll();
        setError(err instanceof Error ? err.message : ru.calculations.pollError);
      }
    },
    [stopPoll],
  );

  const startPoll = useCallback(
    (jobId: string) => {
      stopPoll();
      pollRef.current = window.setInterval(() => {
        void refreshJob(jobId);
      }, POLL_MS);
    },
    [refreshJob, stopPoll],
  );

  const onCreate = async () => {
    if (!lastRevision) {
      setError(ru.calculations.needRevision);
      return;
    }
    if (connectionMode === "offline") {
      setError(ru.calculations.offlineBlocked);
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const created = await createJob(
        {
          revisionId: lastRevision.revisionId,
          snapshotHash: lastRevision.snapshotHash,
        },
        newIdempotencyKey(),
      );
      setJob(created);
      if (!TERMINAL.has(created.status)) {
        startPoll(created.id);
      }
    } catch (err) {
      if (err instanceof NetworkError || err instanceof ApiError) {
        setError(err.message);
      } else {
        setError(ru.calculations.createError);
      }
    } finally {
      setBusy(false);
    }
  };

  const onCancel = async () => {
    if (!job) return;
    setBusy(true);
    setError(null);
    try {
      const next = await cancelJob(job.id);
      setJob(next);
      if (TERMINAL.has(next.status)) {
        stopPoll();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : ru.calculations.cancelError);
    } finally {
      setBusy(false);
    }
  };

  const manifest = job?.resultManifest ?? null;
  const mapAvailable = manifest?.mapAvailable === true;

  return (
    <section className="page">
      <h2>{ru.calculations.title}</h2>
      <p className="page-lead">{ru.calculations.lead}</p>
      <p className="page-hint">{ru.calculations.hint}</p>

      {lastRevision ? (
        <p className="page-meta">
          {ru.calculations.revisionLabel}: {lastRevision.revisionId}
          <br />
          snapshotHash: {lastRevision.snapshotHash}
        </p>
      ) : (
        <p className="page-meta">{ru.calculations.needRevision}</p>
      )}

      <div className="calc-actions">
        <button
          type="button"
          className="btn btn--accent"
          disabled={busy || !lastRevision || connectionMode === "offline"}
          onClick={() => void onCreate()}
        >
          {busy ? ru.calculations.working : ru.calculations.create}
        </button>
        {job && !TERMINAL.has(job.status) ? (
          <button
            type="button"
            className="btn"
            disabled={busy}
            onClick={() => void onCancel()}
          >
            {ru.calculations.cancel}
          </button>
        ) : null}
      </div>

      {error ? <p className="page-error" role="alert">{error}</p> : null}

      {job ? (
        <div className="calc-job" aria-live="polite">
          <h3>{ru.calculations.statusTitle}</h3>
          <dl className="calc-dl">
            <div>
              <dt>jobId</dt>
              <dd>{job.id}</dd>
            </div>
            <div>
              <dt>{ru.calculations.status}</dt>
              <dd>
                <span className={`job-status job-status--${job.status}`}>
                  {job.status}
                </span>
              </dd>
            </div>
            <div>
              <dt>revisionId</dt>
              <dd>{job.revisionId}</dd>
            </div>
            <div>
              <dt>snapshotHash</dt>
              <dd className="mono-wrap">{job.snapshotHash}</dd>
            </div>
            {job.errorCode ? (
              <div>
                <dt>{ru.calculations.errorCode}</dt>
                <dd>
                  {job.errorCode}
                  {job.errorMessage ? ` — ${job.errorMessage}` : ""}
                </dd>
              </div>
            ) : null}
          </dl>

          {job.status === "completed" || manifest ? (
            <div className="calc-manifest">
              <h3>{ru.calculations.manifestTitle}</h3>
              {mapAvailable ? (
                <p className="page-meta">
                  {ru.calculations.artifacts}:{" "}
                  {(manifest?.artifactPaths ?? []).join(", ") || "—"}
                </p>
              ) : (
                <p className="page-hint">{ru.calculations.mapLater}</p>
              )}
              {manifest?.mapDeferredReason ? (
                <p className="page-meta">{manifest.mapDeferredReason}</p>
              ) : null}
              {manifest?.artifactPaths && manifest.artifactPaths.length > 0 ? (
                <ul className="calc-paths">
                  {manifest.artifactPaths.map((p) => (
                    <li key={p}>
                      <code>{p}</code>
                    </li>
                  ))}
                </ul>
              ) : null}
              {manifest?.notes?.length ? (
                <ul className="calc-notes">
                  {manifest.notes.map((n) => (
                    <li key={n}>{n}</li>
                  ))}
                </ul>
              ) : null}
            </div>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
