import { mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import GameListRow from "./GameListRow.vue";
import GameListSkeletonRow from "./GameListSkeletonRow.vue";
import { LIST_COVER_TRACK_PX } from "./listColumns";

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key, locale: { value: "en" } }),
}));

vi.mock("vue-router", async (importOriginal) => ({
  ...(await importOriginal<typeof import("vue-router")>()),
  useRouter: () => ({ push: vi.fn() }),
}));

/** Per-column placeholder geometry: every inline style in the cell, so both
 *  each block's size and its stack's spacing are compared. */
function shapes(row: HTMLElement): string[][] {
  return Array.from(row.children).map((cell) =>
    Array.from(cell.querySelectorAll<HTMLElement>("[style]")).map(
      (el) => el.getAttribute("style") ?? "",
    ),
  );
}

describe("list-mode skeleton row", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
  });

  it("paints the bootstrap row's per-column shapes", () => {
    // The bootstrap row hands over to the pending rows mid-load, so a shape
    // that drifts between them moves the placeholders.
    const pending = mount(GameListRow, { props: { position: 0 } }).element;
    const bootstrap = mount(GameListSkeletonRow).element;

    expect(shapes(pending)).toEqual(shapes(bootstrap));
  });

  it("sizes the cover column off the art cap, not the measured ratios", () => {
    const grid = (row: HTMLElement) => row.style.gridTemplateColumns;
    const pending = mount(GameListRow, { props: { position: 0 } }).element;
    const bootstrap = mount(GameListSkeletonRow).element;

    expect(grid(pending)).toBe(grid(bootstrap));
    expect(grid(pending)).toContain(`${LIST_COVER_TRACK_PX}px`);
  });
});
