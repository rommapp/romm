import { mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { SimpleRom } from "@/v2/stores/galleryRoms";
import GameListRow from "./GameListRow.vue";
import GameListSkeletonRow from "./GameListSkeletonRow.vue";
import { getListColumns, LIST_COVER_TRACK_PX } from "./listColumns";

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

const ROM = {
  id: 1,
  name: "Chrono Trigger",
  fs_name: "Chrono Trigger.sfc",
  fs_name_no_ext: "Chrono Trigger",
  platform_id: 1,
  fs_size_bytes: 4_194_304,
  created_at: "2026-01-02T00:00:00Z",
  languages: [],
  regions: [],
  metadatum: { first_release_date: "1995-08-11", average_rating: 9.1 },
  hltb_metadata: { main_story: 23 },
  rom_user: {},
} as unknown as SimpleRom;

function mountHydratedRow() {
  return mount(GameListRow, {
    props: { rom: ROM },
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
    // The bootstrap row hands over to the pending rows mid-load, so a shape
    // that drifts between them moves the placeholders.
    const pending = mount(GameListRow, { props: { position: 0 } }).element;
    const bootstrap = mount(GameListSkeletonRow).element;

    expect(shapes(pending)).toEqual(shapes(bootstrap));
  });

  it("pins the quantity columns to the right edge in every flavour", () => {
    // The columns decide alignment, the rows only paint it: a cell that
    // stops reading the config drops left while the header above stays right.
    const expected = getListColumns(true).map((col) => col.align === "end");
    const pending = mount(GameListRow, { props: { position: 0 } }).element;
    const hydrated = mountHydratedRow().element;
    const bootstrap = mount(GameListSkeletonRow).element;

    expect(rightEdges(pending)).toEqual(expected);
    expect(rightEdges(hydrated)).toEqual(expected);
    expect(rightEdges(bootstrap)).toEqual(expected);
  });

  it("sizes the cover column off the art cap, not the measured ratios", () => {
    const grid = (row: HTMLElement) => row.style.gridTemplateColumns;
    const pending = mount(GameListRow, { props: { position: 0 } }).element;
    const bootstrap = mount(GameListSkeletonRow).element;

    expect(grid(pending)).toBe(grid(bootstrap));
    expect(grid(pending)).toContain(`${LIST_COVER_TRACK_PX}px`);
  });
});
