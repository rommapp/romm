import { describe, expect, it, vi } from "vitest";
import { computed } from "vue";
import {
  LIST_ROW_DETAIL_HEIGHT_PX,
  LIST_ROW_HEIGHT_PX,
} from "@/v2/components/Gallery/listColumns";
import { useListExpansion } from "./index";

// Reduced motion skips the roll, so the panel lands on its final height in
// one step and the state machine can be read without chasing frames.
vi.mock("@/v2/composables/useReducedMotion", () => ({
  useReducedMotion: () => ({ enabled: computed(() => true) }),
}));

const OPEN_HEIGHT = LIST_ROW_HEIGHT_PX + LIST_ROW_DETAIL_HEIGHT_PX;

describe("useListExpansion", () => {
  it("opens a row's panel and gives it the room", () => {
    const list = useListExpansion();

    list.toggle(3);

    expect(list.isExpanded(3)).toBe(true);
    expect(list.detailHeight(3)).toBe(LIST_ROW_DETAIL_HEIGHT_PX);
    expect(list.rowHeight(3)).toBe(OPEN_HEIGHT);
  });

  it("leaves every other row alone", () => {
    const list = useListExpansion();

    list.toggle(3);

    expect(list.detailHeight(4)).toBe(0);
    expect(list.rowHeight(4)).toBe(LIST_ROW_HEIGHT_PX);
  });

  it("opens one row at a time", () => {
    const list = useListExpansion();

    list.toggle(3);
    list.toggle(7);

    expect(list.isExpanded(3)).toBe(false);
    expect(list.rowHeight(3)).toBe(LIST_ROW_HEIGHT_PX);
    expect(list.rowHeight(7)).toBe(OPEN_HEIGHT);
  });

  it("gives the row its height back when it closes", () => {
    const list = useListExpansion();
    list.toggle(3);

    list.toggle(3);

    expect(list.isExpanded(3)).toBe(false);
    expect(list.rowHeight(3)).toBe(LIST_ROW_HEIGHT_PX);
  });

  it("drops everything when the list underneath changes", () => {
    const list = useListExpansion();
    list.toggle(3);

    list.collapse();

    expect(list.isExpanded(3)).toBe(false);
    expect(list.rowHeight(3)).toBe(LIST_ROW_HEIGHT_PX);
  });
});
