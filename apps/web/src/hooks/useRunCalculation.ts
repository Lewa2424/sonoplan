import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, NetworkError } from "../api/client";
import { createJob, getJob, newIdempotencyKey } from "../api/jobsApi";
import type { JobResponse } from "../api/types";
import { ru } from "../i18n/ru";
import { useEditorStore } from "../store/editorStore";

const TERMINAL = new Set(["completed", "failed", "cancelled"]);
const POLL_MS = 1500;

export function useRunCalculation() {
  const connectionMode = useEditorStore((s) => s.connectionMode);
  const commitRevision = useEditorStore((s) => s.commitRevision);
  const lastCalcJobId = useEditorStore((s) => s.lastCalcJobId);
  const setLastCalcJobId = useEditorStore((s) => s.setLastCalcJobId);
  const applyJobResultToPlan = useEditorStore((s) => s.applyJobResultToPlan);

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
      if (appliedJobIdRef.current === next.id) return;
      appliedJobIdRef.current = next.id;
      applyJobResultToPlan(next);
    },
    [applyJobResultToPlan],
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
