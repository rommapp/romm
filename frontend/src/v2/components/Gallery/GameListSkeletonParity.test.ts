import { mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import GameListRow from "./GameListRow.vue";
import GameListSkeletonRow from "./GameListSkeletonRow.vue";
import { getListColumns, LIST_COVER_TRACK_PX } from "./listColumns";
import { rom } from "./listRowFixture";

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

/** Per-column right-edge flag, in column order. */
function rightEdges(row: HTMLElement): boolean[] {
  return Array.from(row.children).map((cell) =>
    Array.from(cell.classList).some((name) => name.endsWith("--end")),
  );
}

/** Per-column tabular-figure flag, in column order. */
function tabularFigures(row: HTMLElement): boolean[] {
  return Array.from(row.children).map((cell) =>
    cell.classList.contains("game-list-row__cell--num"),
  );
}

function mountHydratedRow() {
  return mount(GameListRow, {
    props: { rom: rom() },
    global: {
      stubs: {
        GameActionBtn: true,
        GameCard: true,
        RCheckbox: true,
        RChip: true,
        RPlatformIcon: true,
        RTooltip: true,
        SiblingBadge: true,
      },
    },
  });
}

describe("list-mode skeleton row", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
  });

  it("paints the bootstrap row's per-column shapes", () => {
    // A shape that drifts across the mid-load handover moves the placeholders.
    const pending = mount(GameListRow, { props: { position: 0 } }).element;
    const bootstrap = mount(GameListSkeletonRow).element;

    expect(shapes(pending)).toEqual(shapes(bootstrap));
  });

  it("pins the quantity columns to the right edge in every flavour", () => {
    // A cell that stops reading the column config drops left under its header.
    const expected = getListColumns(true).map((col) => col.align === "end");
    const pending = mount(GameListRow, { props: { position: 0 } }).element;
    const hydrated = mountHydratedRow().element;
    const bootstrap = mount(GameListSkeletonRow).element;

    expect(rightEdges(pending)).toEqual(expected);
    expect(rightEdges(hydrated)).toEqual(expected);
    expect(rightEdges(bootstrap)).toEqual(expected);
  });

  it("renders the numeric columns in tabular figures", () => {
    // Only the hydrated row has digits; nothing else catches a dropped `--num`.
    const expected = getListColumns(true).map((col) => col.numeric === true);
    const hydrated = mountHydratedRow().element;

    expect(tabularFigures(hydrated)).toEqual(expected);
  });

  it("sizes the cover column off the art cap, not the measured ratios", () => {
    const grid = (row: HTMLElement) => row.style.gridTemplateColumns;
    const pending = mount(GameListRow, { props: { position: 0 } }).element;
    const bootstrap = mount(GameListSkeletonRow).element;

    expect(grid(pending)).toBe(grid(bootstrap));
    expect(grid(pending)).toContain(`${LIST_COVER_TRACK_PX}px`);
  });
});
