import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, NetworkError } from "../api/client";
import { cancelJob, createJob, getJob, newIdempotencyKey } from "../api/jobsApi";
import type { JobResponse, PunctualReceiverSummary } from "../api/types";
import { ru } from "../i18n/ru";
import {
  computeLpScale,
  formatLpScaleLegend,
} from "../model/lpPalette";
import { useEditorStore } from "../store/editorStore";

const TERMINAL = new Set(["completed", "failed", "cancelled"]);
const POLL_MS = 1500;

function formatLp(lp: number | null | undefined): string {
  if (lp === null || lp === undefined || Number.isNaN(lp)) {
    return "— (null)";
  }
  return `${lp.toFixed(1)} дБ`;
}

function formatEnergy(e: number | null | undefined): string {
  if (e === null || e === undefined || Number.isNaN(e)) {
    return "—";
  }
  return e.toExponential(3);
}

function confirmedReceivers(
  list: readonly PunctualReceiverSummary[] | undefined,
): PunctualReceiverSummary[] {
  if (!list) return [];
  return list.filter((p) => p.lpDbGlobal !== null && p.lpDbGlobal !== undefined);
}

export function CalculationsPage() {
  const lastRevision = useEditorStore((s) => s.lastRevision);
  const connectionMode = useEditorStore((s) => s.connectionMode);
  const commitRevision = useEditorStore((s) => s.commitRevision);
  const applyPunctualLpToWorkplaces = useEditorStore(
    (s) => s.applyPunctualLpToWorkplaces,
  );
  const applySurfaceMapFromManifest = useEditorStore(
    (s) => s.applySurfaceMapFromManifest,
  );
  const planLpOverlay = useEditorStore((s) => s.planLpOverlay);
  const isPlanResultStale = useEditorStore((s) => s.isPlanResultStale);
  const lastCalcJobId = useEditorStore((s) => s.lastCalcJobId);
  const setLastCalcJobId = useEditorStore((s) => s.setLastCalcJobId);

  const [job, setJob] = useState<JobResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pollRef = useRef<number | null>(null);
  const appliedJobIdRef = useRef<string | null>(null);
  const restoredRef = useRef(false);

  const stopPoll = useCallback(() => {
    if (pollRef.current !== null) {
      window.clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  useEffect(() => () => stopPoll(), [stopPoll]);

  const applyLevelsFromJob = useCallback(
    (next: JobResponse) => {
      if (next.status !== "completed") return;
      const manifest = next.resultManifest;
      const punctual = confirmedReceivers(manifest?.punctualReceivers);
      const hasMap = manifest?.mapAvailable === true;
      if (punctual.length === 0 && !hasMap) return;
      if (appliedJobIdRef.current === next.id) return;
      appliedJobIdRef.current = next.id;
      const mode = manifest?.executionMode;
      const exportMeta = (manifest as { exportMeta?: { mode?: string } } | null)
        ?.exportMeta;
      const usedBoxExport = exportMeta?.mode === "export_box";
      if (punctual.length > 0) {
        applyPunctualLpToWorkplaces({
          jobId: next.id,
          revisionId: next.revisionId,
          // Honesty: fixture/demo vs box export from revision AABB.
          fixtureReplay:
            mode === "fixture_replay" ||
            (mode === "github_actions_spps" && !usedBoxExport),
          punctual,
        });
      }
      const grid = (
        manifest as {
          grid?: {
            originX?: number;
            originY?: number;
            cellSizeM?: number;
            cellSizeYM?: number;
            nx?: number;
            ny?: number;
            zM?: number;
            lpDb?: (number | null)[];
          } | null;
        } | null
      )?.grid;
      if (
        manifest?.mapAvailable === true &&
        grid &&
        typeof grid.originX === "number" &&
        typeof grid.originY === "number" &&
        typeof grid.cellSizeM === "number" &&
        typeof grid.nx === "number" &&
        typeof grid.ny === "number" &&
        Array.isArray(grid.lpDb)
      ) {
        applySurfaceMapFromManifest({
          jobId: next.id,
          revisionId: next.revisionId,
          grid: {
            originX: grid.originX,
            originY: grid.originY,
            cellSizeM: grid.cellSizeM,
            cellSizeYM: grid.cellSizeYM,
            nx: grid.nx,
            ny: grid.ny,
            zM: grid.zM,
            lpDb: grid.lpDb,
          },
        });
      }
    },
    [applyPunctualLpToWorkplaces, applySurfaceMapFromManifest],
  );

  const refreshJob = useCallback(
    async (jobId: string) => {
      try {
        const next = await getJob(jobId);
        setJob(next);
        applyLevelsFromJob(next);
        if (TERMINAL.has(next.status)) {
          stopPoll();
        }
      } catch (err) {
        stopPoll();
        setError(err instanceof Error ? err.message : ru.calculations.pollError);
      }
    },
    [applyLevelsFromJob, stopPoll],
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

  // Restore last job when returning to the tab (local useState is cleared on unmount).
  useEffect(() => {
    if (restoredRef.current) return;
    if (!lastCalcJobId || connectionMode === "offline") return;
    restoredRef.current = true;
    void (async () => {
      try {
        const next = await getJob(lastCalcJobId);
        setJob(next);
        applyLevelsFromJob(next);
        if (!TERMINAL.has(next.status)) {
          startPoll(next.id);
        }
      } catch {
        setLastCalcJobId(null);
      }
    })();
  }, [
    applyLevelsFromJob,
    connectionMode,
    lastCalcJobId,
    setLastCalcJobId,
    startPoll,
  ]);

  const onCommitRevision = async () => {
    if (connectionMode === "offline") {
      setError(ru.calculations.offlineBlocked);
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await commitRevision();
      const rev = useEditorStore.getState().lastRevision;
      if (!rev) {
        setError(
          useEditorStore.getState().syncMessage ?? ru.calculations.revisionError,
        );
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : ru.calculations.revisionError);
    } finally {
      setBusy(false);
    }
  };

  const runJobForRevision = async (revisionId: string, snapshotHash: string) => {
    const created = await createJob(
      { revisionId, snapshotHash },
      newIdempotencyKey(),
    );
    setLastCalcJobId(created.id);
    setJob(created);
    applyLevelsFromJob(created);
    if (!TERMINAL.has(created.status)) {
      startPoll(created.id);
    }
  };

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
      await runJobForRevision(
        lastRevision.revisionId,
        lastRevision.snapshotHash,
      );
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

  /** One-click: save draft → revision → job (online only). */
  const onReviseAndRun = async () => {
    if (connectionMode === "offline") {
      setError(ru.calculations.offlineBlocked);
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await commitRevision();
      const rev = useEditorStore.getState().lastRevision;
      if (!rev) {
        setError(
          useEditorStore.getState().syncMessage ?? ru.calculations.revisionError,
        );
        return;
      }
      await runJobForRevision(rev.revisionId, rev.snapshotHash);
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
  const punctual = confirmedReceivers(manifest?.punctualReceivers);
  const hasLevels = punctual.length > 0;
  const execMode = manifest?.executionMode;
  const isReplay = execMode === "fixture_replay";
  const isActions =
    execMode === "github_actions_spps" ||
    execMode === "github_actions_pending";
  const isPending =
    !job ||
    job.status === "queued" ||
    job.status === "running" ||
    execMode === "github_actions_pending";

  const stale = isPlanResultStale();
  let bannerText: string;
  if (!job) {
    bannerText = ru.calculations.levelsIdle;
  } else if (stale && (hasLevels || mapAvailable)) {
    bannerText = ru.calculations.levelsStale;
  } else if (hasLevels) {
    const exportMeta = (
      manifest as { exportMeta?: { mode?: string } } | null
    )?.exportMeta;
    bannerText = isReplay
      ? ru.calculations.levelsReplay
      : isActions
        ? exportMeta?.mode === "export_box"
          ? ru.calculations.levelsActionsBox
          : ru.calculations.levelsActions
        : ru.calculations.levelsReady;
  } else if (isPending) {
    bannerText = ru.calculations.levelsPending;
  } else {
    bannerText = ru.calculations.levelsBlocked;
  }

  const bannerOk = hasLevels;

  return (
    <section className="page">
      <h2>{ru.calculations.title}</h2>
      <p className="page-lead">{ru.calculations.lead}</p>
      <p
        className={bannerOk ? "page-banner page-banner--ok" : "page-banner"}
        role="status"
      >
        {bannerText}
      </p>
      <p className="page-hint">{ru.calculations.hint}</p>

      {connectionMode === "offline" ? (
        <p className="page-meta" role="status">
          {ru.calculations.offlineBlocked}
        </p>
      ) : null}

      {lastRevision ? (
        <p className="page-meta">
          {ru.calculations.revisionLabel}: {lastRevision.revisionId}
          <br />
          snapshotHash: {lastRevision.snapshotHash}
        </p>
      ) : (
        <p className="page-meta">{ru.calculations.needRevision}</p>
      )}

      {planLpOverlay ? (
        <p className="page-meta" role="status">
          {ru.calculations.planOverlayOn}
          {planLpOverlay.fixtureReplay
            ? ` (${ru.calculations.planOverlayReplay})`
            : ""}
        </p>
      ) : null}

      <div className="calc-actions">
        {connectionMode === "online" && !lastRevision ? (
          <button
            type="button"
            className="btn"
            disabled={busy}
            onClick={() => void onCommitRevision()}
          >
            {busy ? ru.calculations.working : ru.calculations.commitRevision}
          </button>
        ) : null}
        <button
          type="button"
          className="btn btn--accent"
          disabled={busy || connectionMode === "offline"}
          onClick={() =>
            void (lastRevision ? onCreate() : onReviseAndRun())
          }
        >
          {busy
            ? ru.calculations.working
            : lastRevision
              ? ru.calculations.create
              : ru.calculations.reviseAndRun}
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

          {hasLevels ? (
            <div className="calc-levels">
              <h3>{ru.calculations.levelsTitle}</h3>
              <div className="calc-table-wrap">
                <table className="calc-table">
                  <thead>
                    <tr>
                      <th scope="col">{ru.calculations.receiver}</th>
                      <th scope="col">{ru.calculations.energy}</th>
                      <th scope="col">{ru.calculations.lpDb}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {punctual.map((p) => (
                      <tr
                        key={
                          p.receiverId ??
                          p.relativePath ??
                          String(p.lpDbGlobal)
                        }
                      >
                        <td>{p.receiverId ?? "—"}</td>
                        <td className="mono-wrap">
                          {formatEnergy(p.energySumGlobal)}
                        </td>
                        <td>{formatLp(p.lpDbGlobal)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ) : null}

          {job.status === "completed" || manifest ? (
            <div className="calc-manifest">
              <h3>{ru.calculations.manifestTitle}</h3>
              {mapAvailable ? (
                <>
                  <p className="page-meta">{ru.calculations.mapReady}</p>
                  <p className="page-meta">
                    {ru.calculations.mapLegend}:{" "}
                    {(() => {
                      const g = (
                        manifest as {
                          grid?: { lpDb?: (number | null)[] } | null;
                        } | null
                      )?.grid;
                      const scale = g?.lpDb ? computeLpScale(g.lpDb) : null;
                      return scale
                        ? formatLpScaleLegend(scale)
                        : ru.calculations.mapLegendHint;
                    })()}
                  </p>
                  <p className="page-hint">{ru.calculations.mapLegendHint}</p>
                </>
              ) : (
                <>
                  <p className="page-hint">{ru.calculations.mapLater}</p>
                  {!hasLevels ? (
                    <p className="page-meta">{ru.calculations.noFakeLevels}</p>
                  ) : null}
                </>
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
