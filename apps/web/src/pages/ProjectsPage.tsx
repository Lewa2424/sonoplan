import { ru } from "../i18n/ru";

export function ProjectsPage() {
  return (
    <section className="page">
      <h2>{ru.projects.title}</h2>
      <p className="page-lead">{ru.projects.empty}</p>
      <p className="page-hint">{ru.projects.hint}</p>
    </section>
  );
}
