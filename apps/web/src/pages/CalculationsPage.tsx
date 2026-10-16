import { ru } from "../i18n/ru";
import { useEditorStore } from "../store/editorStore";

export function CalculationsPage() {
  const lastRevision = useEditorStore((s) => s.lastRevision);

  return (
    <section className="page">
      <h2>{ru.calculations.title}</h2>
      <p className="page-lead">{ru.calculations.needSpps}</p>
      <p className="page-hint">{ru.calculations.hint}</p>
      {lastRevision ? (
        <p className="page-meta">
          Последняя ревизия сессии: {lastRevision.revisionId}
          <br />
          snapshotHash: {lastRevision.snapshotHash}
          <br />
          Расчёт не запущен — нет worker/SPPS (STG-04).
        </p>
      ) : (
        <p className="page-meta">
          Ревизия не зафиксирована. Сначала модель → «Ревизия».
        </p>
      )}
    </section>
  );
}
