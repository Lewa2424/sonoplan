import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, NetworkError } from "../api/client";
import { createJob, getJob, newIdempotencyKey } from "../api/jobsApi";
import type { JobResponse, ResultManifestStub } from "../api/types";
import { ru } from "../i18n/ru";
import { useEditorStore } from "../store/editorStore";

const TERMINAL = new Set(["completed", "failed", "cancelled"]);
const POLL_MS = 1500;

function confirmedPunctual(manifest: ResultManifestStub | null | undefined) {
  const list = manifest?.punctualReceivers;
  if (!list) return [];
  return list.filter((p) => p.lpDbGlobal !== null && p.lpDbGlobal !== undefined);
}

export function useRunCalculation() {
  const connectionMode = useEditorStore((s) => s.connectionMode);
  const commitRevision = useEditorStore((s) => s.commitRevision);
  const lastCalcJobId = useEditorStore((s) => s.lastCalcJobId);
  const setLastCalcJobId = useEditorStore((s) => s.setLastCalcJobId);
  const applyPunctualLpToWorkplaces = useEditorStore(
    (s) => s.applyPunctualLpToWorkplaces,
  );
  const applySurfaceMapFromManifest = useEditorStore(
    (s) => s.applySurfaceMapFromManifest,
  );

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

  const applyFromJob = useCallback(
    (next: JobResponse) => {
      if (next.status !== "completed") return;
      const manifest = next.resultManifest;
      if (appliedJobIdRef.current === next.id) return;
      appliedJobIdRef.current = next.id;

      const punctual = confirmedPunctual(manifest);
      const mode = manifest?.executionMode;
      const exportMeta = (
        manifest as { exportMeta?: { mode?: string } } | null
      )?.exportMeta;
      const usedBoxExport = exportMeta?.mode === "export_box";
      if (punctual.length > 0) {
        applyPunctualLpToWorkplaces({
          jobId: next.id,
          revisionId: next.revisionId,
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
        applyFromJob(next);
        if (TERMINAL.has(next.status)) stopPoll();
      } catch (err) {
        stopPoll();
        setError(err instanceof Error ? err.message : ru.calculations.pollError);
      }
    },
    [applyFromJob, stopPoll],
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

  useEffect(() => () => stopPoll(), [stopPoll]);

  useEffect(() => {
    if (restoredRef.current) return;
    if (!lastCalcJobId || connectionMode === "offline") return;
    restoredRef.current = true;
    void (async () => {
      try {
        const next = await getJob(lastCalcJobId);
        setJob(next);
        applyFromJob(next);
        if (!TERMINAL.has(next.status)) {
          startPoll(next.id);
        }
      } catch {
        setLastCalcJobId(null);
      }
    })();
  }, [
    applyFromJob,
    connectionMode,
    lastCalcJobId,
    setLastCalcJobId,
    startPoll,
  ]);

  const runJobForRevision = async (revisionId: string, snapshotHash: string) => {
    const created = await createJob(
      { revisionId, snapshotHash },
      newIdempotencyKey(),
    );
    setLastCalcJobId(created.id);
    setJob(created);
    applyFromJob(created);
    if (!TERMINAL.has(created.status)) {
      startPoll(created.id);
    }
  };

  /** Зафиксировать ревизию (если нужно) и запустить расчёт. */
  const reviseAndRun = async () => {
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

  return {
    job,
    setJob,
    busy,
    error,
    setError,
    reviseAndRun,
    stopPoll,
    refreshJob,
    startPoll,
    applyFromJob,
  };
}
