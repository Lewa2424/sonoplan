import { useEffect, useRef } from "react";
import { Link, useParams } from "react-router-dom";
import { PROJECT_SCHEMA_VERSION } from "@sonoplan/domain";
import { EditorToolbar } from "../components/EditorToolbar";
import { PlanCanvas } from "../components/PlanCanvas";
import { PropertiesPanel } from "../components/PropertiesPanel";
import { ValidationList } from "../components/ValidationList";
import { useElementSize } from "../hooks/useElementSize";
import { ru } from "../i18n/ru";
import { useEditorStore } from "../store/editorStore";

export function ModelPage() {
  const { projectId } = useParams<{ projectId?: string }>();
  const storeProjectId = useEditorStore((s) => s.projectId);
  const connectionMode = useEditorStore((s) => s.connectionMode);
  const projectName = useEditorStore((s) => s.projectName);
  const syncStatus = useEditorStore((s) => s.syncStatus);
  const syncMessage = useEditorStore((s) => s.syncMessage);
  const lastRevision = useEditorStore((s) => s.lastRevision);
  const model = useEditorStore((s) => s.model);
  const loadOnlineProject = useEditorStore((s) => s.loadOnlineProject);
  const saveDraft = useEditorStore((s) => s.saveDraft);

  const canvasHostRef = useRef<HTMLDivElement>(null);
  const { width, height } = useElementSize(canvasHostRef);

  useEffect(() => {
    if (
      projectId &&
      projectId !== "offline" &&
      projectId !== storeProjectId
    ) {
      void loadOnlineProject(projectId).catch(() => {
        /* syncMessage already set */
      });
    }
  }, [projectId, storeProjectId, loadOnlineProject]);

  useEffect(() => {
    if (connectionMode !== "online" || syncStatus !== "dirty") return;
    const t = window.setTimeout(() => {
      void saveDraft();
    }, 800);
    return () => window.clearTimeout(t);
  }, [connectionMode, syncStatus, saveDraft, model]);

  const activeId = storeProjectId ?? projectId;
  if (!activeId) {
    return (
      <section className="page">
        <h2>{ru.model.title}</h2>
        <p className="page-lead">{ru.model.noProject}</p>
        <Link className="btn btn--accent" to="/projects">
          {ru.nav.projects}
        </Link>
      </section>
    );
  }

  return (
    <section className="page page--model">
      <header className="model-header">
        <div>
          <h2>{ru.model.title}</h2>
          <p className="page-meta">
            {projectName}
            {connectionMode === "offline" && (
              <span className="badge badge--offline"> offline</span>
            )}
          </p>
        </div>
        <p className="sync-line" data-status={syncStatus}>
          {syncLabel(syncStatus)}
        </p>
      </header>

      <EditorToolbar />

      {syncMessage && (
        <p
          className={
            syncStatus === "conflict" || syncStatus === "error"
              ? "banner banner--error"
              : "banner"
          }
        >
          {syncMessage}
        </p>
      )}

      {lastRevision && (
        <p className="banner banner--ok">
          Последняя ревизия готова к расчёту (
          {lastRevision.revisionId.slice(0, 8)}…)
        </p>
      )}

      <p className="view-tabs">
        <span className="view-tab view-tab--active">{ru.model.viewTop}</span>
        <span className="view-tab view-tab--disabled" title={ru.model.todo3d}>
          3D
        </span>
      </p>

      <div className="model-layout">
        <div className="plan-host" ref={canvasHostRef}>
          <PlanCanvas width={width} height={height} />
        </div>
        <PropertiesPanel />
      </div>

      <ValidationList />

      <p className="page-hint">{ru.model.hint}</p>
      <p className="page-meta">schemaVersion: {PROJECT_SCHEMA_VERSION}</p>
    </section>
  );
}

function syncLabel(status: string): string {
  switch (status) {
    case "saved":
      return ru.sync.saved;
    case "dirty":
    case "saving":
      return ru.sync.dirty;
    case "conflict":
      return ru.sync.conflict;
    case "offline":
      return ru.sync.offline;
    case "loading":
      return ru.projects.loading;
    default:
      return status;
  }
}
