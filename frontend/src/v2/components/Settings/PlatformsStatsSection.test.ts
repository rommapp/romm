import { mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Platform } from "@/stores/platforms";
import storePlatforms from "@/stores/platforms";
import PlatformsStatsSection from "./PlatformsStatsSection.vue";

// vue-i18n's `t` is stubbed to echo the key so the component mounts without
// the full i18n plugin.
vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

// The heartbeat store pulls in config + i18n; stub it down to the single
// method this component calls.
vi.mock("@/stores/heartbeat", () => ({
  default: () => ({ getMetadataOptionsByPriority: () => [] }),
}));

function platform(overrides: Partial<Platform> = {}): Platform {
  return {
    id: 1,
    slug: "snes",
    fs_slug: "snes",
    rom_count: 1,
    name: "Super Nintendo",
    igdb_slug: null,
    moby_slug: null,
    hltb_slug: null,
    libretro_slug: null,
    custom_name: "",
    description: null,
    created_at: "",
    updated_at: "",
    fs_size_bytes: 0,
    is_unidentified: false,
    is_identified: true,
    missing_from_fs: false,
    display_name: "Super Nintendo",
    firmware_count: 0,
    ...overrides,
  } as Platform;
}

function mountSection(platforms: Platform[]) {
  storePlatforms().set(platforms);
  return mount(PlatformsStatsSection, {
    props: { totalFilesize: 0, metadataCoverage: {}, regionBreakdown: {} },
    global: {
      stubs: {
        RIcon: true,
        RPlatformIcon: true,
        RProgressLinear: true,
        RSliderBtnGroup: true,
        RTextField: true,
      },
    },
  });
}

type Section = ReturnType<typeof mountSection>;

function renderedNames(wrapper: Section): string[] {
  return wrapper.findAll(".r-v2-plat-stats__name").map((n) => n.text());
}

function rowCount(wrapper: Section): number {
  return wrapper.findAll(".r-v2-plat-stats__row").length;
}

async function setOrder(wrapper: Section, order: "name" | "size" | "count") {
  (wrapper.vm as unknown as { orderBy: string }).orderBy = order;
  await wrapper.vm.$nextTick();
}

async function setSearch(wrapper: Section, query: string) {
  (wrapper.vm as unknown as { searchQuery: string }).searchQuery = query;
  await wrapper.vm.$nextTick();
}

// Real-world libraries keep official and "(Unofficial)" / headered-vs-headerless
// sets of the same system side by side. Those variants share one metadata slug
// while their id and fs_slug stay unique, so this fixture reproduces the shared
// slugs (nes x2, genesis x2) that broke keyed rendering. The unique-slug Atari
// and Xbox bookends keep the shared-slug rows in the interior, where a search
// narrowing corrupts the keyed list under a non-unique key.
function duplicateSlugLibrary(): Platform[] {
  return [
    platform({
      id: 1,
      slug: "atari2600",
      fs_slug: "atari2600",
      name: "Atari 2600",
      display_name: "Atari 2600",
      rom_count: 3,
      fs_size_bytes: 5,
    }),
    platform({
      id: 2,
      slug: "nes",
      fs_slug: "nes",
      name: "Nintendo Entertainment System",
      display_name: "Nintendo Entertainment System",
      rom_count: 5,
      fs_size_bytes: 10,
    }),
    platform({
      id: 3,
      slug: "nes",
      fs_slug: "nes-unofficial",
      name: "Nintendo Entertainment System (Unofficial)",
      display_name: "Nintendo Entertainment System (Unofficial)",
      rom_count: 1,
      fs_size_bytes: 40,
    }),
    platform({
      id: 4,
      slug: "genesis",
      fs_slug: "genesis",
      name: "Sega Genesis",
      display_name: "Sega Genesis",
      rom_count: 4,
      fs_size_bytes: 20,
    }),
    platform({
      id: 5,
      slug: "genesis",
      fs_slug: "genesis-unofficial",
      name: "Sega Genesis (Unofficial)",
      display_name: "Sega Genesis (Unofficial)",
      rom_count: 2,
      fs_size_bytes: 30,
    }),
    platform({
      id: 6,
      slug: "xbox",
      fs_slug: "xbox",
      name: "Xbox",
      display_name: "Xbox",
      rom_count: 6,
      fs_size_bytes: 6,
    }),
  ];
}

describe("PlatformsStatsSection", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
  });

  it("renders one row per platform on initial load", () => {
    const wrapper = mountSection(duplicateSlugLibrary());
    expect(rowCount(wrapper)).toBe(6);
    expect(renderedNames(wrapper)).toEqual([
      "Atari 2600",
      "Nintendo Entertainment System",
      "Nintendo Entertainment System (Unofficial)",
      "Sega Genesis",
      "Sega Genesis (Unofficial)",
      "Xbox",
    ]);
  });

  // Re-sorting is a pure reorder of the same set. With a non-unique key, Vue
  // cannot match old rows to new ones and leaves stale DOM behind, so the row
  // count grows past the library size with every click. Each sort must simply
  // reorder the same four rows.
  it("keeps one row per platform when re-sorting a library with shared slugs", async () => {
    const wrapper = mountSection(duplicateSlugLibrary());

    await setOrder(wrapper, "size");
    expect(rowCount(wrapper)).toBe(6);
    expect(renderedNames(wrapper)).toEqual([
      "Nintendo Entertainment System (Unofficial)", // 40
      "Sega Genesis (Unofficial)", // 30
      "Sega Genesis", // 20
      "Nintendo Entertainment System", // 10
      "Xbox", // 6
      "Atari 2600", // 5
    ]);

    await setOrder(wrapper, "count");
    expect(rowCount(wrapper)).toBe(6);
    expect(renderedNames(wrapper)).toEqual([
      "Xbox", // 6
      "Nintendo Entertainment System", // 5
      "Sega Genesis", // 4
      "Atari 2600", // 3
      "Sega Genesis (Unofficial)", // 2
      "Nintendo Entertainment System (Unofficial)", // 1
    ]);

    await setOrder(wrapper, "name");
    expect(rowCount(wrapper)).toBe(6);
    expect(renderedNames(wrapper)).toEqual([
      "Atari 2600",
      "Nintendo Entertainment System",
      "Nintendo Entertainment System (Unofficial)",
      "Sega Genesis",
      "Sega Genesis (Unofficial)",
      "Xbox",
    ]);
  });

  // Searching narrows then widens the list; widening back re-adds rows that
  // share a slug with survivors, which is what stacks stale DOM under a
  // non-unique key. Every state must show exactly the platforms that match.
  it("keeps one row per platform when searching a library with shared slugs", async () => {
    const wrapper = mountSection(duplicateSlugLibrary());

    // Narrows the full list down to the two interior genesis rows.
    await setSearch(wrapper, "sega");
    expect(rowCount(wrapper)).toBe(2);
    expect(renderedNames(wrapper)).toEqual([
      "Sega Genesis",
      "Sega Genesis (Unofficial)",
    ]);

    await setSearch(wrapper, "nintendo");
    expect(rowCount(wrapper)).toBe(2);
    expect(renderedNames(wrapper)).toEqual([
      "Nintendo Entertainment System",
      "Nintendo Entertainment System (Unofficial)",
    ]);

    // Clearing widens the list back to the full set; the re-added rows must not
    // stack on top of the ones already on screen.
    await setSearch(wrapper, "");
    expect(rowCount(wrapper)).toBe(6);
    expect(renderedNames(wrapper)).toEqual([
      "Atari 2600",
      "Nintendo Entertainment System",
      "Nintendo Entertainment System (Unofficial)",
      "Sega Genesis",
      "Sega Genesis (Unofficial)",
      "Xbox",
    ]);
  });
});
