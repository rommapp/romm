import { describe, expect, it } from "vitest";
import { ref } from "vue";
import { useIdSelection } from "./index";

interface Row {
  id: number;
}

const rows = (...ids: number[]): Row[] => ids.map((id) => ({ id }));

describe("useIdSelection", () => {
  it("toggles one id at a time", () => {
    const s = useIdSelection(() => rows(1, 2, 3));

    s.toggle(2);
    expect(s.isSelected(2)).toBe(true);
    expect(s.selected.value).toEqual([{ id: 2 }]);
    expect(s.count.value).toBe(1);

    s.toggle(2);
    expect(s.isSelected(2)).toBe(false);
    expect(s.count.value).toBe(0);
  });

  it("replaces the set rather than mutating it, so watchers fire", () => {
    const s = useIdSelection(() => rows(1, 2));
    const before = s.selectedIds.value;

    s.toggle(1);

    expect(s.selectedIds.value).not.toBe(before);
    expect(before.has(1)).toBe(false);
  });

  it("reports all and some against the live list", () => {
    const s = useIdSelection(() => rows(1, 2));

    expect(s.allSelected.value).toBe(false);
    expect(s.someSelected.value).toBe(false);

    s.toggle(1);
    expect(s.someSelected.value).toBe(true);
    expect(s.allSelected.value).toBe(false);

    s.toggle(2);
    expect(s.allSelected.value).toBe(true);
    expect(s.someSelected.value).toBe(false);
  });

  it("treats an empty list as nothing selected", () => {
    const s = useIdSelection(() => [] as Row[]);

    expect(s.allSelected.value).toBe(false);
    expect(s.someSelected.value).toBe(false);
  });

  it("selects everything, then clears when everything already is", () => {
    const s = useIdSelection(() => rows(1, 2, 3));

    s.toggleAll();
    expect(s.count.value).toBe(3);

    s.toggleAll();
    expect(s.count.value).toBe(0);
  });

  it("ignores ids that have left the list", () => {
    const items = ref<Row[]>(rows(1, 2));
    const s = useIdSelection(() => items.value);

    s.toggleAll();
    expect(s.count.value).toBe(2);

    // The row is deleted elsewhere; its stale id must not inflate the count.
    items.value = rows(1);
    expect(s.count.value).toBe(1);
    expect(s.allSelected.value).toBe(true);
    expect(s.selected.value).toEqual([{ id: 1 }]);
  });
});
