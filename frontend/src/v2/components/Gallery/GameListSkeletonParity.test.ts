import { mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { RomMetadataSchema, RomUserSchema } from "@/__generated__";
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

const ROM_USER: RomUserSchema = {
  id: 1,
  user_id: 1,
  rom_id: 1,
  created_at: "2026-01-02T00:00:00Z",
  updated_at: "2026-01-02T00:00:00Z",
  last_played: null,
  is_main_sibling: true,
  backlogged: false,
  now_playing: false,
  hidden: false,
  rating: 0,
  difficulty: 0,
  completion: 0,
  status: null,
};

const METADATUM: RomMetadataSchema = {
  rom_id: 1,
  genres: [],
  franchises: [],
  collections: [],
  companies: [],
  publishers: [],
  developers: [],
  game_modes: [],
  age_ratings: [],
  player_count: "1",
  first_release_date: Date.UTC(1995, 7, 11),
  average_rating: 9.1,
};

/** A complete `SimpleRom`, so a new required field breaks the build instead of
 *  hiding behind a cast. Tests override only the fields they read. */
const ROM_DEFAULTS: SimpleRom = {
  id: 1,
  igdb_id: null,
  sgdb_id: null,
  moby_id: null,
  ss_id: null,
  ra_id: null,
  launchbox_id: null,
  hasheous_id: null,
  tgdb_id: null,
  flashpoint_id: null,
  hltb_id: null,
  demozoo_id: null,
  pouet_id: null,
  csdb_id: null,
  steam_id: null,
  gamelist_id: null,
  libretro_id: null,
  platform_id: 1,
  platform_slug: "snes",
  platform_fs_slug: "snes",
  platform_custom_name: null,
  platform_display_name: "Super Nintendo",
  fs_name: "Chrono Trigger.sfc",
  fs_name_no_tags: "Chrono Trigger",
  fs_name_no_ext: "Chrono Trigger",
  fs_extension: "sfc",
  fs_path: "snes/Chrono Trigger.sfc",
  fs_size_bytes: 4_194_304,
  name: "Chrono Trigger",
  name_sort_key: "chrono trigger",
  slug: "chrono-trigger",
  summary: null,
  alternative_names: [],
  youtube_video_id: null,
  metadatum: METADATUM,
  igdb_metadata: null,
  moby_metadata: null,
  ss_metadata: null,
  launchbox_metadata: null,
  hasheous_metadata: null,
  flashpoint_metadata: null,
  hltb_metadata: { main_story: 23 },
  demozoo_metadata: null,
  pouet_metadata: null,
  csdb_metadata: null,
  steam_metadata: null,
  gamelist_metadata: null,
  manual_metadata: null,
  path_cover_small: null,
  path_cover_large: null,
  url_cover: null,
  has_manual: false,
  has_soundtrack: false,
  path_manual: null,
  url_manual: null,
  path_video: null,
  is_unidentified: false,
  is_identified: true,
  revision: null,
  regions: ["USA"],
  languages: ["en"],
  tags: [],
  crc_hash: null,
  md5_hash: null,
  sha1_hash: null,
  ra_hash: null,
  title_id: null,
  save_target: null,
  save_target_layout: null,
  has_simple_single_file: true,
  has_nested_single_file: false,
  has_multiple_files: false,
  full_path: "/romm/library/snes/Chrono Trigger.sfc",
  created_at: "2026-01-02T00:00:00Z",
  updated_at: "2026-01-02T00:00:00Z",
  missing_from_fs: false,
  is_physical: false,
  has_file_on_disk: true,
  upc: null,
  has_notes: false,
  rom_user: ROM_USER,
  merged_screenshots: [],
  merged_ra_metadata: null,
  files: [],
  sibling_roms: [],
};

function rom(overrides: Partial<SimpleRom> = {}): SimpleRom {
  return { ...ROM_DEFAULTS, ...overrides };
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
