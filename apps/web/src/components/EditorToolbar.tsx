import { useNavigate } from "react-router-dom";
import { useRunCalculation } from "../hooks/useRunCalculation";
import { ru } from "../i18n/ru";
import { useEditorStore } from "../store/editorStore";

export function EditorToolbar() {
  const toolMode = useEditorStore((s) => s.toolMode);
  const applyRectangleRoom = useEditorStore((s) => s.applyRectangleRoom);
  const applyLShapeRoom = useEditorStore((s) => s.applyLShapeRoom);
  const beginPolygon = useEditorStore((s) => s.beginPolygon);
  const finishPolygon = useEditorStore((s) => s.finishPolygon);
  const cancelPolygon = useEditorStore((s) => s.cancelPolygon);
  const runValidate = useEditorStore((s) => s.runValidate);
  const saveDraft = useEditorStore((s) => s.saveDraft);
  const reloadDraft = useEditorStore((s) => s.reloadDraft);
  const syncStatus = useEditorStore((s) => s.syncStatus);
  const connectionMode = useEditorStore((s) => s.connectionMode);
  const polygonDraft = useEditorStore((s) => s.polygonDraft);
  const navigate = useNavigate();
  const { reviseAndRun, busy, error } = useRunCalculation();

  const onCalculate = async () => {
    await reviseAndRun();
    navigate("/calculations");
  };

  return (
    <div className="editor-toolbar" role="toolbar" aria-label="Инструменты модели">
      <div className="toolbar-row">
        <button type="button" className="btn" onClick={applyRectangleRoom}>
          □ Прямоуг.
        </button>
        <button type="button" className="btn" onClick={applyLShapeRoom}>
          L-форма
        </button>
        {toolMode === "drawPolygon" ? (
          <>
            <button
              type="button"
              className="btn btn--accent"
              onClick={finishPolygon}
              disabled={polygonDraft.length < 3}
            >
              Готово ({polygonDraft.length})
            </button>
            <button type="button" className="btn" onClick={cancelPolygon}>
              Отмена
            </button>
          </>
        ) : (
          <button type="button" className="btn" onClick={beginPolygon}>
            Многоуг.
          </button>
        )}
        <button
          type="button"
          className="btn btn--accent"
          onClick={() => void runValidate()}
        >
          Проверить
        </button>
        <button
          type="button"
          className="btn btn--accent"
          onClick={() => void onCalculate()}
          disabled={connectionMode !== "online" || busy}
        >
          {busy ? ru.calculations.working : ru.model.calculate}
        </button>
        <button
          type="button"
          className="btn"
          onClick={() => void saveDraft()}
          disabled={connectionMode !== "online"}
        >
          Сохранить
        </button>
        {syncStatus === "conflict" && (
          <button
            type="button"
            className="btn btn--warn"
            onClick={() => void reloadDraft()}
          >
            Перезагрузить
          </button>
        )}
      </div>
      {error ? <p className="banner banner--error">{error}</p> : null}
    </div>
  );
}
