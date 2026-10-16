import { ru } from "../i18n/ru";

export function CalculationsPage() {
  return (
    <section className="page">
      <h2>{ru.calculations.title}</h2>
      <p className="page-lead">{ru.calculations.empty}</p>
      <p className="page-hint">{ru.calculations.hint}</p>
    </section>
  );
}
