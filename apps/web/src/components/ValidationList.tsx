import { useEditorStore } from "../store/editorStore";

export function ValidationList() {
  const issues = useEditorStore((s) => s.validationIssues);
  if (issues.length === 0) {
    return null;
  }
  return (
    <ul className="validation-list" aria-label="Результаты проверки">
      {issues.map((issue, i) => (
        <li
          key={`${issue.code}-${i}`}
          className={
            issue.severity === "error"
              ? "validation-item validation-item--error"
              : "validation-item validation-item--warn"
          }
        >
          <span className="validation-sev">
            {issue.severity === "error" ? "ошибка" : "предупр."}
          </span>
          <span>
            [{issue.code}] {issue.message}
          </span>
        </li>
      ))}
    </ul>
  );
}
