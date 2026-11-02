/* eslint-disable vue/one-component-per-file */
import { mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { defineComponent, ref } from "vue";
import GalleryToolbar from "@/components/Gallery/GalleryToolbar.vue";
import PlatformFilterDrawer, {
  type PlatformFacet,
} from "@/components/Platforms/PlatformFilterDrawer.vue";
import storePlatforms, { type Platform } from "@/stores/platforms";
import { platformFixture } from "@/utils/platform.fixtures";
import PlatformsIndex from "./PlatformsIndex.vue";

vi.mock("vue-i18n");

// Plain object rather than a reactive route: every test sets the query
// before mounting, which is when the view reads it.
const { routeState, searchState } = vi.hoisted(() => ({
  routeState: { query: {} as Record<string, string> },
  searchState: { term: "" },
}));

vi.mock("vue-router", async (importOriginal) => ({
  ...(await importOriginal<typeof import("vue-router")>()),
  useRoute: () => routeState,
  useRouter: () => ({ replace: vi.fn() }),
}));

vi.mock("@/lib", () => ({
  RDivider: defineComponent({ template: "<hr />" }),
  RLetterHeading: defineComponent({
    props: { label: { type: String, default: "" } },
    template: "<h2>{{ label }}</h2>",
  }),
  REmptyState: defineComponent({
    props: { title: { type: String, default: "" } },
    template: '<div class="empty-state">{{ title }}</div>',
  }),
  RSkeletonBlock: defineComponent({ template: "<div />" }),
}));

vi.mock("@/components/Gallery/GalleryToolbar.vue", () => ({
  default: defineComponent({
    props: { filterActiveCount: { type: Number, default: 0 } },
    template: "<div />",
  }),
}));

vi.mock("@/components/Platforms/PlatformFilterDrawer.vue", () => ({
  default: defineComponent({
    props: { facets: { type: Array, default: () => [] } },
    template: "<div />",
  }),
}));

vi.mock("@/components/Platforms/PlatformListHeader.vue", () => ({
  default: defineComponent({ template: "<div />" }),
}));

vi.mock("@/components/Platforms/PlatformListRow.vue", () => ({
  default: defineComponent({
    props: {
      displayName: { type: String, default: "" },
      romCount: { type: Number, default: 0 },
    },
    template:
      '<div class="platform-row">{{ displayName }} {{ romCount }}</div>',
  }),
}));

vi.mock("@/components/Platforms/PlatformTile.vue", () => ({
  default: defineComponent({
    props: {
      displayName: { type: String, default: "" },
      romCount: { type: Number, default: 0 },
    },
    template:
      '<div class="platform-tile">{{ displayName }} {{ romCount }}</div>',
  }),
}));

vi.mock("@/components/shared/IndexShell.vue", () => ({
  default: defineComponent({
    template:
      '<main><slot name="header" /><slot name="toolbar" /><slot name="listHeader" /><slot name="listRows" /><slot /></main>',
  }),
}));

vi.mock("@/components/shared/PageHeader.vue", () => ({
  default: defineComponent({
    props: {
      title: { type: String, default: "" },
      count: { type: Number, default: 0 },
    },
    template: "<header>{{ title }} {{ count }}</header>",
  }),
}));

// Mutable so a test can select a non-default groupBy/layout before
// mounting, mirroring how routeState works for the route query above.
const { galleryModeState } = vi.hoisted(() => ({
  galleryModeState: { groupBy: "none", layout: "grid" },
}));

vi.mock("@/composables/useGalleryMode", () => ({
  useGalleryMode: () => ({
    groupBy: ref(galleryModeState.groupBy),
    layout: ref(galleryModeState.layout),
  }),
}));

vi.mock("@/composables/useGalleryViewModeUrl", () => ({
  useGalleryViewModeUrl: vi.fn(),
}));

// Slugs the mocked composable treats as streaming-capable.
const { streamableSlugs, nativeSlugs } = vi.hoisted(() => ({
  streamableSlugs: new Set<string>(),
  nativeSlugs: new Set<string>(),
}));

vi.mock("@/composables/usePlatformPlayable", () => ({
  usePlatformPlayableChecker: () => ({
    isPlayable: ref(() => false),
    isStreamable: ref((slug: string | null | undefined) =>
      slug ? streamableSlugs.has(slug) : false,
    ),
    isNativeSupported: ref((slug: string | null | undefined) =>
      slug ? nativeSlugs.has(slug) : false,
    ),
  }),
}));

vi.mock("@/composables/useTileSearchUrl", () => ({
  useTileSearchUrl: () => ref(searchState.term),
}));

vi.mock("@/composables/useGridNav", () => ({
  useGridNav: vi.fn(),
}));

function platform(
  id: number,
  displayName: string,
  romCount: number,
  overrides: Partial<Platform> = {},
): Platform {
  return platformFixture({
    id,
    name: displayName,
    slug: displayName.toLowerCase().replaceAll(" ", "-"),
    rom_count: romCount,
    ...overrides,
  });
}

describe("PlatformsIndex", () => {
  beforeEach(() => {
    routeState.query = {};
    galleryModeState.groupBy = "none";
    galleryModeState.layout = "grid";
    streamableSlugs.clear();
    nativeSlugs.clear();
    searchState.term = "";
  });

  it("hides empty platforms by default", () => {
    const platforms = storePlatforms();
    platforms.set([platform(2, "Nintendo 64", 12), platform(1, "Game Boy", 0)]);

    const wrapper = mount(PlatformsIndex);

    expect(wrapper.text()).toContain("common.platforms 1");
    expect(wrapper.text()).toContain("Nintendo 64 12");
    expect(wrapper.text()).not.toContain("Game Boy 0");
  });

  it("renders empty database platforms when ?show=all, so they stay reachable", () => {
    routeState.query = { show: "all" };
    const platforms = storePlatforms();
    platforms.set([platform(2, "Nintendo 64", 12), platform(1, "Game Boy", 0)]);

    const wrapper = mount(PlatformsIndex);

    expect(wrapper.text()).toContain("common.platforms 2");
    expect(wrapper.text()).toContain("Game Boy 0");
    expect(wrapper.text()).toContain("Nintendo 64 12");
  });

  it("points at the filter when every platform is empty", () => {
    const platforms = storePlatforms();
    platforms.set([platform(1, "Game Boy", 0)]);

    const wrapper = mount(PlatformsIndex);

    expect(wrapper.text()).toContain("platform.no-platforms-with-games");
  });

  // Inside the desktop shell a platform with no in-browser core and no
  // container is still playable, PS2 being the case the feature exists for.
  it("counts a native-only platform as playable when grouping by playable", () => {
    galleryModeState.groupBy = "playable";
    nativeSlugs.add("ps2");
    const platforms = storePlatforms();
    platforms.set([platform(1, "PlayStation 2", 5, { slug: "ps2" })]);

    const wrapper = mount(PlatformsIndex);

    const headings = wrapper
      .findAll(".r-pidx__group-heading")
      .map((h) => h.text());
    expect(headings).toContain("platform.playable");
    expect(headings).not.toContain("platform.not-playable");
  });

  it("counts a streaming-only platform as playable when grouping by playable", () => {
    galleryModeState.groupBy = "playable";
    streamableSlugs.add("dreamcast");
    const platforms = storePlatforms();
    platforms.set([platform(1, "Dreamcast", 5)]);

    const wrapper = mount(PlatformsIndex);

    const headings = wrapper
      .findAll(".r-pidx__group-heading")
      .map((h) => h.text());
    expect(headings).toContain("platform.playable");
    expect(headings).not.toContain("platform.not-playable");
  });

  describe("search", () => {
    function seed() {
      storePlatforms().set([
        platform(1, "PlayStation", 30, {
          slug: "ps",
          fs_slug: "psx",
          category: "console",
          family_name: "PlayStation",
        }),
        platform(2, "Nintendo 64", 12, {
          slug: "n64",
          fs_slug: "nintendo-64",
          category: "console",
          family_name: "Nintendo",
          abbreviation: "N64",
          alternative_names: ["Ultra 64"],
        }),
        platform(3, "Game Boy Advance", 5, {
          slug: "gba",
          fs_slug: "gba-roms",
          category: "portable_console",
          family_name: "Nintendo",
        }),
      ]);
    }

    it("matches on the display name", () => {
      seed();
      searchState.term = "advance";

      const wrapper = mount(PlatformsIndex);

      expect(wrapper.text()).toContain("Game Boy Advance 5");
      expect(wrapper.text()).not.toContain("PlayStation 30");
      expect(wrapper.text()).not.toContain("Nintendo 64 12");
    });

    it("matches on the slug", () => {
      seed();
      searchState.term = "n64";

      const wrapper = mount(PlatformsIndex);

      expect(wrapper.text()).toContain("Nintendo 64 12");
      expect(wrapper.text()).not.toContain("PlayStation 30");
      expect(wrapper.text()).not.toContain("Game Boy Advance 5");
    });

    it("matches on the folder name", () => {
      seed();
      searchState.term = "psx";

      const wrapper = mount(PlatformsIndex);

      expect(wrapper.text()).toContain("PlayStation 30");
      expect(wrapper.text()).not.toContain("Nintendo 64 12");
      expect(wrapper.text()).not.toContain("Game Boy Advance 5");
    });

    it("matches on the raw category", () => {
      seed();
      searchState.term = "portable_console";

      const wrapper = mount(PlatformsIndex);

      expect(wrapper.text()).toContain("Game Boy Advance 5");
      expect(wrapper.text()).not.toContain("PlayStation 30");
      expect(wrapper.text()).not.toContain("Nintendo 64 12");
    });

    // The category the user reads is the prettified label, so typing what
    // the list column and the group heading show has to match too.
    it("matches on the prettified category label", () => {
      seed();
      searchState.term = "portable console";

      const wrapper = mount(PlatformsIndex);

      expect(wrapper.text()).toContain("Game Boy Advance 5");
      expect(wrapper.text()).not.toContain("PlayStation 30");
      expect(wrapper.text()).not.toContain("Nintendo 64 12");
    });

    it("matches on the family name", () => {
      seed();
      searchState.term = "nintendo";

      const wrapper = mount(PlatformsIndex);

      expect(wrapper.text()).toContain("Game Boy Advance 5");
      expect(wrapper.text()).toContain("Nintendo 64 12");
      expect(wrapper.text()).not.toContain("PlayStation 30");
    });

    it("matches on an alternative name", () => {
      seed();
      searchState.term = "ultra";

      const wrapper = mount(PlatformsIndex);

      expect(wrapper.text()).toContain("Nintendo 64 12");
      expect(wrapper.text()).not.toContain("PlayStation 30");
      expect(wrapper.text()).not.toContain("Game Boy Advance 5");
    });

    it("matches a renamed platform on its original name", () => {
      storePlatforms().set([
        platform(1, "Game Boy Advance", 7, {
          custom_name: "My Handhelds",
          display_name: "My Handhelds",
          slug: "gba",
          fs_slug: "gba",
        }),
        platform(2, "PlayStation", 30, { slug: "ps", fs_slug: "psx" }),
      ]);
      searchState.term = "advance";

      const wrapper = mount(PlatformsIndex);

      expect(wrapper.text()).toContain("My Handhelds 7");
      expect(wrapper.text()).not.toContain("PlayStation 30");
    });

    it("ignores case and surrounding whitespace", () => {
      seed();
      searchState.term = "  PSX  ";

      const wrapper = mount(PlatformsIndex);

      expect(wrapper.text()).toContain("PlayStation 30");
      expect(wrapper.text()).not.toContain("Nintendo 64 12");
    });

    it("reports no results when nothing matches any field", () => {
      seed();
      searchState.term = "sega";

      const wrapper = mount(PlatformsIndex);

      expect(wrapper.text()).toContain("platform.no-platforms-search");
      expect(wrapper.text()).not.toContain("PlayStation 30");
    });

    it("tolerates platforms with no category or family", () => {
      storePlatforms().set([
        platform(1, "Arcade", 7, {
          slug: "arcade",
          fs_slug: "arcade",
          category: null,
          family_name: null,
        }),
      ]);
      searchState.term = "arcade";

      const wrapper = mount(PlatformsIndex);

      expect(wrapper.text()).toContain("Arcade 7");
    });
  });

  describe("facets", () => {
    function seed() {
      streamableSlugs.add("gba");
      storePlatforms().set([
        platform(1, "PlayStation", 30, {
          slug: "ps",
          category: "console",
          generation: 5,
          family_slug: "playstation",
          family_name: "PlayStation",
        }),
        platform(2, "Nintendo 64", 12, {
          slug: "n64",
          category: "console",
          generation: 5,
          family_slug: "nintendo",
          family_name: "Nintendo",
        }),
        platform(3, "Game Boy Advance", 5, {
          slug: "gba",
          category: "portable_console",
          generation: 6,
          family_slug: "nintendo",
          family_name: "Nintendo",
        }),
      ]);
    }

    function facet(
      wrapper: ReturnType<typeof mount>,
      key: string,
    ): PlatformFacet | undefined {
      const facets = wrapper
        .findComponent(PlatformFilterDrawer)
        .props("facets") as PlatformFacet[];
      return facets.find((f) => f.key === key);
    }

    it("ORs values picked in one facet", () => {
      seed();
      routeState.query = { category: "portable_console,console" };

      const wrapper = mount(PlatformsIndex);

      expect(wrapper.text()).toContain("PlayStation 30");
      expect(wrapper.text()).toContain("Game Boy Advance 5");
    });

    it("ANDs across facets", () => {
      seed();
      routeState.query = { category: "console", family: "nintendo" };

      const wrapper = mount(PlatformsIndex);

      expect(wrapper.text()).toContain("Nintendo 64 12");
      expect(wrapper.text()).not.toContain("PlayStation 30");
      expect(wrapper.text()).not.toContain("Game Boy Advance 5");
      expect(wrapper.text()).toContain("common.platforms 3");
    });

    it("filters by play mode", () => {
      seed();
      routeState.query = { play: "stream" };

      const wrapper = mount(PlatformsIndex);

      expect(wrapper.text()).toContain("Game Boy Advance 5");
      expect(wrapper.text()).not.toContain("Nintendo 64 12");
    });

    it("counts each facet's options against the other facets", () => {
      seed();
      routeState.query = { family: "nintendo", gen: "5" };

      const wrapper = mount(PlatformsIndex);

      expect(facet(wrapper, "category")?.options).toEqual([
        { value: "console", label: "Console", count: 1 },
        { value: "portable_console", label: "Portable Console", count: 0 },
      ]);
      expect(facet(wrapper, "generation")?.options).toEqual([
        { value: "5", label: "5th generation", count: 1 },
        { value: "6", label: "6th generation", count: 1 },
      ]);
      expect(facet(wrapper, "family")?.selected).toEqual(["nintendo"]);
    });

    it("only offers play modes some platform supports", () => {
      seed();

      const wrapper = mount(PlatformsIndex);

      expect(facet(wrapper, "play")?.options).toEqual([
        { value: "stream", label: "platform.play-mode-stream", count: 1 },
      ]);
    });

    it("falls back to the raw value for an unknown play mode", () => {
      seed();
      routeState.query = { play: "__proto__" };

      const wrapper = mount(PlatformsIndex);

      expect(facet(wrapper, "play")?.options).toContainEqual({
        value: "__proto__",
        label: "__proto__",
        count: 0,
      });
    });

    it("badges the toolbar filter button with the active facet count", () => {
      seed();
      routeState.query = {
        category: "console,portable_console",
        play: "stream",
      };

      const wrapper = mount(PlatformsIndex);

      expect(
        wrapper.findComponent(GalleryToolbar).props("filterActiveCount"),
      ).toBe(2);
    });

    it("says the filters matched nothing", () => {
      seed();
      routeState.query = { category: "portable_console", gen: "5" };

      const wrapper = mount(PlatformsIndex);

      expect(wrapper.text()).toContain("platform.no-platforms-filters");
    });
  });
});
