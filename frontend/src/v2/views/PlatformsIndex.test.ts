/* eslint-disable vue/one-component-per-file */
import { mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { defineComponent, ref } from "vue";
import storePlatforms, { type Platform } from "@/stores/platforms";
import PlatformsIndex from "./PlatformsIndex.vue";

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

// Plain object rather than a reactive route: every test sets the query
// before mounting, which is when the view reads it.
const { routeState } = vi.hoisted(() => ({
  routeState: { query: {} as Record<string, string> },
}));

vi.mock("vue-router", async (importOriginal) => ({
  ...(await importOriginal<typeof import("vue-router")>()),
  useRoute: () => routeState,
  useRouter: () => ({ replace: vi.fn() }),
}));

vi.mock("@v2/lib", () => ({
  RDivider: defineComponent({ template: "<hr />" }),
  RLetterHeading: defineComponent({
    props: { label: { type: String, default: "" } },
    template: "<h2>{{ label }}</h2>",
  }),
  RSkeletonBlock: defineComponent({ template: "<div />" }),
}));

vi.mock("@/v2/components/Gallery/GalleryToolbar.vue", () => ({
  default: defineComponent({ template: "<div />" }),
}));

vi.mock("@/v2/components/Platforms/PlatformListHeader.vue", () => ({
  default: defineComponent({ template: "<div />" }),
}));

vi.mock("@/v2/components/Platforms/PlatformListRow.vue", () => ({
  default: defineComponent({
    props: {
      displayName: { type: String, default: "" },
      romCount: { type: Number, default: 0 },
    },
    template:
      '<div class="platform-row">{{ displayName }} {{ romCount }}</div>',
  }),
}));

vi.mock("@/v2/components/Platforms/PlatformTile.vue", () => ({
  default: defineComponent({
    props: {
      displayName: { type: String, default: "" },
      romCount: { type: Number, default: 0 },
    },
    template:
      '<div class="platform-tile">{{ displayName }} {{ romCount }}</div>',
  }),
}));

vi.mock("@/v2/components/shared/EmptyState.vue", () => ({
  default: defineComponent({
    props: { message: { type: String, default: "" } },
    template: '<div class="empty-state">{{ message }}</div>',
  }),
}));

vi.mock("@/v2/components/shared/IndexShell.vue", () => ({
  default: defineComponent({
    template:
      '<main><slot name="header" /><slot name="toolbar" /><slot name="listHeader" /><slot /></main>',
  }),
}));

vi.mock("@/v2/components/shared/PageHeader.vue", () => ({
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

vi.mock("@/v2/composables/useGalleryMode", () => ({
  useGalleryMode: () => ({
    groupBy: ref(galleryModeState.groupBy),
    layout: ref(galleryModeState.layout),
  }),
}));

vi.mock("@/v2/composables/useGalleryViewModeUrl", () => ({
  useGalleryViewModeUrl: vi.fn(),
}));

// Slugs the mocked composable treats as streaming-capable.
const { streamableSlugs } = vi.hoisted(() => ({
  streamableSlugs: new Set<string>(),
}));

vi.mock("@/v2/composables/usePlatformPlayable", () => ({
  usePlatformPlayableChecker: () => ({
    isPlayable: ref(() => false),
    isStreamable: ref((slug: string | null | undefined) =>
      slug ? streamableSlugs.has(slug) : false,
    ),
    getMode: ref(() => null),
  }),
}));

vi.mock("@/v2/composables/useTileSearchUrl", () => ({
  useTileSearchUrl: () => ref(""),
}));

vi.mock("@/v2/composables/useWrapGridNav", () => ({
  useWrapGridNav: vi.fn(),
}));

function platform(id: number, displayName: string, romCount: number): Platform {
  return {
    id,
    display_name: displayName,
    name: displayName,
    slug: displayName.toLowerCase().replaceAll(" ", "-"),
    fs_slug: displayName.toLowerCase().replaceAll(" ", "-"),
    rom_count: romCount,
  } as Platform;
}

describe("PlatformsIndex", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    routeState.query = {};
    galleryModeState.groupBy = "none";
    galleryModeState.layout = "grid";
    streamableSlugs.clear();
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

  it("counts a streaming-only platform as playable when grouping by playable", () => {
    galleryModeState.groupBy = "playable";
    streamableSlugs.add("dreamcast");
    const platforms = storePlatforms();
    platforms.set([platform(1, "Dreamcast", 5)]);

    const wrapper = mount(PlatformsIndex);

    const headings = wrapper
      .findAll(".r-v2-pidx__group-heading")
      .map((h) => h.text());
    expect(headings).toContain("Playable");
    expect(headings).not.toContain("Not playable");
  });
});
