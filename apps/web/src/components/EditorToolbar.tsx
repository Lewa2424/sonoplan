import { useEditorStore } from "../store/editorStore";

export function EditorToolbar() {
  const toolMode = useEditorStore((s) => s.toolMode);
  const setToolMode = useEditorStore((s) => s.setToolMode);
  const applyRectangleRoom = useEditorStore((s) => s.applyRectangleRoom);
  const applyLShapeRoom = useEditorStore((s) => s.applyLShapeRoom);
  const beginPolygon = useEditorStore((s) => s.beginPolygon);
  const finishPolygon = useEditorStore((s) => s.finishPolygon);
  const cancelPolygon = useEditorStore((s) => s.cancelPolygon);
  const runValidate = useEditorStore((s) => s.runValidate);
  const commitRevision = useEditorStore((s) => s.commitRevision);
  const saveDraft = useEditorStore((s) => s.saveDraft);
  const reloadDraft = useEditorStore((s) => s.reloadDraft);
  const syncStatus = useEditorStore((s) => s.syncStatus);
  const connectionMode = useEditorStore((s) => s.connectionMode);
  const polygonDraft = useEditorStore((s) => s.polygonDraft);

  return (
    <div className="editor-toolbar" role="toolbar" aria-label="Инструменты модели">
      <div className="toolbar-row">
        <button
          type="button"
          className={toolMode === "select" ? "btn btn--active" : "btn"}
          onClick={() => setToolMode("select")}
        >
          Выбор
        </button>
        <button
          type="button"
          className={toolMode === "move" ? "btn btn--active" : "btn"}
          onClick={() => setToolMode("move")}
        >
          Переместить
        </button>
      </div>
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
      </div>
      <div className="toolbar-row">
        <button type="button" className="btn btn--accent" onClick={() => void runValidate()}>
          Проверить
        </button>
        <button
          type="button"
          className="btn btn--accent"
          onClick={() => void commitRevision()}
          disabled={connectionMode !== "online"}
        >
          Ревизия
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
    </div>
  );
}
