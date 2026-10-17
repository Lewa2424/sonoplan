import { beforeEach, describe, expect, it } from "vitest";
import { useEditorStore } from "./editorStore";

describe("deleteSelected", () => {
  beforeEach(() => {
    const s = useEditorStore.getState();
    s.reset();
    s.openOffline("Тест");
  });

  it("removes only the selected source and keeps its nearby workplace", () => {
    const s = useEditorStore.getState();
    s.setPlaceWithWorkplace(true);
    s.addEquipmentAt(3, 3, "lathe");
    const before = useEditorStore.getState().model;
    const target = useEditorStore.getState().selection;
    expect(target?.kind).toBe("source");

    useEditorStore.getState().deleteSelected();

    const after = useEditorStore.getState();
    expect(after.model.sources).toHaveLength(before.sources.length - 1);
    expect(after.model.sources.some((x) => x.id === target?.id)).toBe(false);
    expect(after.model.workplaces).toHaveLength(before.workplaces.length);
    expect(after.selection).toBeNull();
  });

  it("removes the selected workplace and obstacle", () => {
    const s = useEditorStore.getState();
    s.addWorkplace(2, 2);
    const wpId = useEditorStore.getState().selection?.id;
    useEditorStore.getState().deleteSelected();
    expect(useEditorStore.getState().model.workplaces.some((w) => w.id === wpId)).toBe(false);

    useEditorStore.getState().addSolidAt(5, 5, "rack");
    const solidId = useEditorStore.getState().selection?.id;
    useEditorStore.getState().deleteSelected();
    expect(useEditorStore.getState().model.solids.some((x) => x.id === solidId)).toBe(false);
  });

  it("never deletes the room", () => {
    const room = useEditorStore.getState().model.rooms[0];
    expect(room).toBeDefined();
    useEditorStore.getState().setSelection({ kind: "room", id: room!.id });
    useEditorStore.getState().deleteSelected();
    expect(useEditorStore.getState().model.rooms).toHaveLength(1);
  });
});
