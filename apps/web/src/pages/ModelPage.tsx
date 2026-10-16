import { PROJECT_SCHEMA_VERSION } from "@sonoplan/domain";
import { ru } from "../i18n/ru";

export function ModelPage() {
  return (
    <section className="page">
      <h2>{ru.model.title}</h2>
      <p className="page-lead">{ru.model.empty}</p>
      <p className="page-hint">{ru.model.hint}</p>
      <p className="page-meta">schemaVersion: {PROJECT_SCHEMA_VERSION}</p>
    </section>
  );
}
