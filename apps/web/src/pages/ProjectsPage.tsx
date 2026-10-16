import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { NetworkError } from "../api/client";
import { API_BASE_URL } from "../api/config";
import { checkApiHealth, createProject, listProjects } from "../api/projectsApi";
import { ru } from "../i18n/ru";
import { useEditorStore } from "../store/editorStore";

export function ProjectsPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const openOffline = useEditorStore((s) => s.openOffline);
  const loadOnlineProject = useEditorStore((s) => s.loadOnlineProject);
  const [name, setName] = useState("Цех 1");
  const [actionError, setActionError] = useState<string | null>(null);

  const healthQuery = useQuery({
    queryKey: ["api-health"],
    queryFn: checkApiHealth,
    retry: false,
    staleTime: 15_000,
  });

  const projectsQuery = useQuery({
    queryKey: ["projects"],
    queryFn: listProjects,
    retry: false,
    enabled: healthQuery.data === true,
  });

  const createMut = useMutation({
    mutationFn: (projectName: string) => createProject(projectName),
    onSuccess: async (project) => {
      await queryClient.invalidateQueries({ queryKey: ["projects"] });
      await loadOnlineProject(project.id);
      navigate(`/model/${project.id}`);
    },
    onError: (err) => {
      setActionError(
        err instanceof Error ? err.message : "Не удалось создать проект",
      );
    },
  });

  const onCreate = (e: FormEvent) => {
    e.preventDefault();
    setActionError(null);
    const trimmed = name.trim();
    if (!trimmed) return;
    createMut.mutate(trimmed);
  };

  const onOpenOnline = async (id: string) => {
    setActionError(null);
    try {
      await loadOnlineProject(id);
      navigate(`/model/${id}`);
    } catch (err) {
      setActionError(
        err instanceof Error ? err.message : "Не удалось открыть проект",
      );
    }
  };

  const onOffline = () => {
    const trimmed = name.trim() || "Локальный цех";
    openOffline(trimmed);
    navigate("/model/offline");
  };

  const apiDown =
    healthQuery.isError ||
    healthQuery.data === false ||
    projectsQuery.error instanceof NetworkError;

  return (
    <section className="page page--projects">
      <h2>{ru.projects.title}</h2>
      <p className="page-hint">{ru.projects.hint}</p>
      <p className="api-status" data-ok={healthQuery.data === true}>
        {healthQuery.isLoading
          ? ru.projects.loading
          : healthQuery.data
            ? `${ru.projects.apiOk} · ${API_BASE_URL}`
            : `${ru.projects.apiError} · ${API_BASE_URL}`}
      </p>

      <form className="project-form" onSubmit={onCreate}>
        <label className="field">
          <span>Название</span>
          <input
            type="text"
            value={name}
            placeholder={ru.projects.namePlaceholder}
            onChange={(e) => setName(e.target.value)}
            autoComplete="off"
          />
        </label>
        <div className="toolbar-row">
          <button
            type="submit"
            className="btn btn--accent"
            disabled={createMut.isPending || apiDown}
          >
            {ru.projects.create}
          </button>
          <button type="button" className="btn" onClick={onOffline}>
            {ru.projects.offline}
          </button>
        </div>
      </form>

      {apiDown && (
        <p className="banner banner--warn">
          API недоступен. Можно продолжить в режиме{" "}
          <strong>{ru.projects.offlineBadge}</strong> — только UI-черновик, без
          PATCH/ревизий.
        </p>
      )}

      {actionError && <p className="banner banner--error">{actionError}</p>}

      {projectsQuery.isLoading && <p>{ru.projects.loading}</p>}

      {projectsQuery.data && projectsQuery.data.length === 0 && (
        <p className="page-lead">{ru.projects.empty}</p>
      )}

      {projectsQuery.data && projectsQuery.data.length > 0 && (
        <ul className="project-list">
          {projectsQuery.data.map((p) => (
            <li key={p.id} className="project-item">
              <div>
                <div className="project-name">{p.name}</div>
                <div className="project-meta">
                  {p.id.slice(0, 8)}… · schema {p.schemaVersion}
                  {p.currentRevisionId
                    ? ` · rev ${p.currentRevisionId.slice(0, 8)}…`
                    : " · без ревизии"}
                </div>
              </div>
              <button
                type="button"
                className="btn btn--accent"
                onClick={() => void onOpenOnline(p.id)}
              >
                {ru.projects.open}
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
