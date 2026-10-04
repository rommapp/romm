import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import { createI18n } from "vue-i18n";
import type { MetadataCoverageItem } from "@/__generated__/models/MetadataCoverageItem";
import type { RegionBreakdownItem } from "@/__generated__/models/RegionBreakdownItem";
import enSettings from "@/locales/en_US/settings.json";
import storeConfig from "@/stores/config";
import type { Platform } from "@/stores/platforms";
import storePlatforms from "@/stores/platforms";
import { makePlatform } from "@/utils/platform.fixtures";
import PlatformsStatsSection from "./PlatformsStatsSection.vue";

const push = vi.fn();
vi.mock("vue-router", async (importOriginal) => ({
  ...(await importOriginal<typeof import("vue-router")>()),
  useRouter: () => ({ push }),
}));

// Real messages rather than a key-echoing stub, so plural selection is
// exercised the way it renders in the app.
const i18n = createI18n({
  legacy: false,
  locale: "en_US",
  fallbackLocale: "en_US",
  messages: { en_US: { settings: enSettings } },
});

function mountSection(
  platforms: Platform[],
  regionBreakdown: Record<string, RegionBreakdownItem[]> = {},
  metadataCoverage: Record<string, MetadataCoverageItem[]> = {},
) {
  storePlatforms().set(platforms);
  return mount(PlatformsStatsSection, {
    props: { totalFilesize: 0, metadataCoverage, regionBreakdown },
    global: {
      plugins: [i18n],
      stubs: {
        RIcon: true,
        PlatformIcon: true,
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

function renderedCounts(wrapper: Section): string[] {
  return wrapper.findAll(".r-v2-plat-stats__count").map((n) => n.text());
}

function rowCount(wrapper: Section): number {
  return wrapper.findAll(".r-v2-plat-stats__row").length;
}

function mountCoverage(items: MetadataCoverageItem[]): Section {
  return mountSection(
    [makePlatform({ id: 1, rom_count: 4 })],
    {},
    { "1": items },
  );
}

function coverageLogos(wrapper: Section): (string | undefined)[] {
  return wrapper
    .findAll(".r-v2-plat-stats__coverage img")
    .map((img) => img.attributes("src"));
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
    makePlatform({
      id: 1,
      slug: "atari2600",
      name: "Atari 2600",
      rom_count: 3,
      fs_size_bytes: 5,
    }),
    makePlatform({
      id: 2,
      slug: "nes",
      name: "Nintendo Entertainment System",
      rom_count: 5,
      fs_size_bytes: 10,
    }),
    makePlatform({
      id: 3,
      slug: "nes",
      fs_slug: "nes-unofficial",
      name: "Nintendo Entertainment System (Unofficial)",
      rom_count: 1,
      fs_size_bytes: 40,
    }),
    makePlatform({
      id: 4,
      slug: "genesis",
      name: "Sega Genesis",
      rom_count: 4,
      fs_size_bytes: 20,
    }),
    makePlatform({
      id: 5,
      slug: "genesis",
      fs_slug: "genesis-unofficial",
      name: "Sega Genesis (Unofficial)",
      rom_count: 2,
      fs_size_bytes: 30,
    }),
    makePlatform({
      id: 6,
      slug: "xbox",
      name: "Xbox",
      rom_count: 6,
      fs_size_bytes: 6,
    }),
  ];
}

describe("PlatformsStatsSection", () => {
  it("links each row to its platform gallery", async () => {
    const wrapper = mountSection(duplicateSlugLibrary());

    const rows = wrapper.findAll(".r-v2-plat-stats__row");
    expect(rows.map((r) => r.attributes("href"))).toEqual([
      "/platform/1",
      "/platform/2",
      "/platform/3",
      "/platform/4",
      "/platform/5",
      "/platform/6",
    ]);
    expect(rows[0]?.attributes("aria-label")).toBe("Open Atari 2600");

    await rows[3]!.trigger("click", { button: 0 });
    expect(push).toHaveBeenCalledWith("/platform/4");
  });

  // The regions toggle sits inside the row anchor, so its click must not
  // bubble into a navigation.
  it("expands regions without navigating to the platform", async () => {
    const regions = [
      { region: "us", count: 5 },
      { region: "eu", count: 4 },
      { region: "jp", count: 3 },
      { region: "au", count: 2 },
      { region: "br", count: 1 },
      { region: "ca", count: 1 },
    ];
    const wrapper = mountSection([makePlatform({ id: 7, rom_count: 16 })], {
      "7": regions,
    });

    expect(wrapper.findAll(".r-v2-plat-stats__region")).toHaveLength(5);

    await wrapper.find(".r-v2-plat-stats__more").trigger("click");

    expect(wrapper.findAll(".r-v2-plat-stats__region")).toHaveLength(
      regions.length,
    );
    expect(push).not.toHaveBeenCalled();
  });

  it("shows the TheGamesDB name and logo on its coverage chip", () => {
    const chip = mountCoverage([{ source: "tgdb", matched: 2 }]).find(
      ".r-v2-plat-stats__coverage",
    );

    expect(chip.find("img").attributes("src")).toBe(
      "/assets/scrappers/tgdb.png",
    );
    expect(chip.attributes("title")).toBe("TheGamesDB matches: 2 / 4");
    expect(chip.text()).toBe("50%");
  });

  it("orders coverage chips by the configured scan priority", () => {
    storeConfig().config.SCAN_METADATA_PRIORITY = ["ss", "tgdb", "igdb"];
    const wrapper = mountCoverage([
      { source: "igdb", matched: 2 },
      { source: "ss", matched: 3 },
      { source: "tgdb", matched: 1 },
    ]);

    expect(coverageLogos(wrapper)).toEqual([
      "/assets/scrappers/ss.png",
      "/assets/scrappers/tgdb.png",
      "/assets/scrappers/igdb.png",
    ]);
  });

  it("orders sources missing from the scan priority by registry order", () => {
    storeConfig().config.SCAN_METADATA_PRIORITY = ["ss"];
    const wrapper = mountCoverage([
      { source: "tgdb", matched: 1 },
      { source: "igdb", matched: 2 },
      { source: "ss", matched: 3 },
    ]);

    expect(coverageLogos(wrapper)).toEqual([
      "/assets/scrappers/ss.png",
      "/assets/scrappers/igdb.png",
      "/assets/scrappers/tgdb.png",
    ]);
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

  it("uses the singular game label for a platform holding exactly one", () => {
    const wrapper = mountSection([
      makePlatform({ id: 1, name: "Atari 2600", rom_count: 1 }),
      makePlatform({ id: 2, name: "Xbox", rom_count: 6 }),
    ]);

    expect(renderedCounts(wrapper)).toEqual(["1 game", "6 games"]);
  });

  it("lists only platforms that contain games, hiding empty leftovers", () => {
    const wrapper = mountSection([
      makePlatform({
        id: 1,
        slug: "snes",
        name: "Super Nintendo",
        rom_count: 5,
      }),
      // Ghost platform: emptied long ago, still in the DB with 0 games.
      makePlatform({
        id: 2,
        slug: "xbox360-hacks",
        name: "Xbox360 Hacks",
        rom_count: 0,
      }),
      makePlatform({
        id: 3,
        slug: "genesis",
        name: "Genesis",
        rom_count: 3,
      }),
    ]);

    const names = renderedNames(wrapper);
    expect(names).toEqual(["Genesis", "Super Nintendo"]);
    expect(names).not.toContain("Xbox360 Hacks");
    expect(wrapper.findAll(".r-v2-plat-stats__row")).toHaveLength(2);
  });

  it("renders no rows when every platform is empty", () => {
    const wrapper = mountSection([
      makePlatform({ id: 1, rom_count: 0 }),
      makePlatform({
        id: 2,
        slug: "genesis",
        name: "Genesis",
        rom_count: 0,
      }),
    ]);

    expect(wrapper.findAll(".r-v2-plat-stats__row")).toHaveLength(0);
    expect(wrapper.findComponent({ name: "REmptyState" }).exists()).toBe(true);
  });

  // Re-sorting is a pure reorder of the same set. With a non-unique key, Vue
  // cannot match old rows to new ones and leaves stale DOM behind, so the row
  // count grows past the library size with every click. Each sort must simply
  // reorder the same six rows.
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
