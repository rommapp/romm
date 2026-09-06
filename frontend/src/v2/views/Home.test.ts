/* eslint-disable vue/one-component-per-file */
import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { defineComponent, ref } from "vue";
import storeCollections, { type Collection } from "@/stores/collections";
import storePlatforms, { type Platform } from "@/stores/platforms";
import storeRoms, { type SimpleRom } from "@/stores/roms";
import { useStreamingStore, type JoinableSession } from "@/stores/streaming";
import Home from "./Home.vue";

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

const { getLibraryInfo } = vi.hoisted(() => ({
  getLibraryInfo: vi.fn(),
}));

vi.mock("@/services/api/setup", () => ({
  default: { getLibraryInfo },
}));

vi.mock("@v2/lib", () => ({
  RChip: defineComponent({ template: "<span><slot /></span>" }),
  RDivider: defineComponent({ template: "<hr />" }),
  RIcon: defineComponent({ template: "<i />" }),
  RSkeletonBlock: defineComponent({ template: "<div />" }),
}));

vi.mock("@/v2/components/Collections/CollectionTile.vue", () => ({
  default: defineComponent({ template: "<div />" }),
}));

vi.mock("@/v2/components/GameCard", () => ({
  GameCard: defineComponent({ template: "<div />" }),
  GameCardSkeleton: defineComponent({ template: "<div />" }),
}));

vi.mock("@/v2/components/shared/CardRow.vue", () => ({
  default: defineComponent({
    props: { title: { type: String, default: "" } },
    template: "<section><h2>{{ title }}</h2><slot /></section>",
  }),
}));

vi.mock("@/v2/components/Home/LiveSessionCard.vue", () => ({
  default: defineComponent({ template: "<div data-test='live' />" }),
}));

vi.mock("@/v2/components/Home/Widgets/WidgetBar.vue", () => ({
  default: defineComponent({ template: "<div />" }),
}));

vi.mock("@/v2/components/Platforms/PlatformTile.vue", () => ({
  default: defineComponent({ template: "<div />" }),
}));

vi.mock("@/v2/composables/useGridNav", () => ({
  useGridNav: vi.fn(),
}));

vi.mock("@/v2/composables/useWebpSupport", () => ({
  useWebpSupport: () => ({
    supportsWebp: ref(false),
    toWebp: (url: string) => url,
  }),
}));

vi.mock("@/composables/useUISettings", () => ({
  useUISettings: () => ({
    showHomeWidgets: ref(true),
    showRecentRoms: ref(true),
    showContinuePlaying: ref(true),
    showPlatforms: ref(true),
    showCollections: ref(true),
    showSmartCollections: ref(false),
    showVirtualCollections: ref(false),
    virtualCollectionType: ref("collection"),
  }),
}));

function platform(id: number): Platform {
  return {
    id,
    display_name: `Platform ${id}`,
    name: `Platform ${id}`,
    slug: `platform-${id}`,
    fs_slug: `platform-${id}`,
    rom_count: 12,
  } as Platform;
}

function collection(id: number): Collection {
  return {
    id,
    name: `Collection ${id}`,
    rom_count: 3,
    rom_ids: [],
  } as unknown as Collection;
}

function rom(id: number): SimpleRom {
  return { id, name: `Rom ${id}` } as SimpleRom;
}

/**
 * Resolve on a later microtask, the way a real request does. Anything
 * asserting on the home page's initial-load ordering has to see the
 * stores fill in after setup, not during it.
 */
async function afterRoundTrip<T>(populate: () => T): Promise<T> {
  await Promise.resolve();
  return populate();
}

/** Wire up every home page fetch; `populated` decides what comes back. */
function stubHomeFetches(populated: boolean) {
  const platforms = storePlatforms();
  const collections = storeCollections();
  const roms = storeRoms();

  vi.spyOn(platforms, "fetchPlatforms").mockImplementation(() => {
    platforms.fetchingPlatforms = true;
    return afterRoundTrip(() => {
      const loaded = populated ? [platform(1)] : [];
      platforms.set(loaded);
      platforms.fetchingPlatforms = false;
      return loaded;
    });
  });

  vi.spyOn(collections, "fetchCollections").mockImplementation(() => {
    collections.fetchingCollections = true;
    return afterRoundTrip(() => {
      const loaded = populated ? [collection(1)] : [];
      collections.setCollections(loaded);
      collections.fetchingCollections = false;
      return loaded;
    });
  });

  vi.spyOn(collections, "fetchSmartCollections").mockImplementation(() => {
    collections.fetchingSmartCollections = true;
    return afterRoundTrip(() => {
      collections.fetchingSmartCollections = false;
      return [];
    });
  });

  vi.spyOn(collections, "fetchVirtualCollections").mockImplementation(() => {
    collections.fetchingVirtualCollections = true;
    return afterRoundTrip(() => {
      collections.fetchingVirtualCollections = false;
      return [];
    });
  });

  vi.spyOn(roms, "fetchRecentRoms").mockImplementation(() =>
    afterRoundTrip(() => {
      const loaded = populated ? [rom(1)] : [];
      roms.setRecentRoms(loaded);
      return loaded;
    }),
  );

  vi.spyOn(roms, "fetchContinuePlayingRoms").mockImplementation(() =>
    afterRoundTrip(() => {
      const loaded = populated ? [rom(2)] : [];
      roms.setContinuePlayingRoms(loaded);
      return loaded;
    }),
  );

  return { platforms, collections, roms };
}

function mountHome() {
  return mount(Home, {
    global: {
      stubs: { RouterLink: defineComponent({ template: "<a><slot /></a>" }) },
    },
  });
}

describe("Home", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    getLibraryInfo.mockReset();
    getLibraryInfo.mockResolvedValue({
      data: { detected_structure: "struct_a", existing_platforms: [] },
    });
  });

  it("never walks the filesystem for a populated library", async () => {
    stubHomeFetches(true);

    const wrapper = mountHome();

    // Setup has run but nothing has resolved: the stores are still empty,
    // which is exactly the transient state that used to fire the request.
    expect(getLibraryInfo).not.toHaveBeenCalled();

    await flushPromises();

    expect(getLibraryInfo).not.toHaveBeenCalled();
    expect(wrapper.text()).not.toContain("home.empty-headline");
  });

  it("fetches the filesystem hint once the library is confirmed empty", async () => {
    stubHomeFetches(false);

    const wrapper = mountHome();
    await flushPromises();

    expect(getLibraryInfo).toHaveBeenCalledTimes(1);
    expect(wrapper.text()).toContain("home.empty-headline");
  });

  it("shows the live row only while someone hosts a multiplayer session", async () => {
    stubHomeFetches(true);
    const streaming = useStreamingStore();
    const fetchJoinable = vi
      .spyOn(streaming, "fetchJoinableSessions")
      .mockResolvedValue(undefined);

    const wrapper = mountHome();
    await flushPromises();

    expect(fetchJoinable).not.toHaveBeenCalled();
    expect(wrapper.text()).not.toContain("home.live-sessions");

    streaming.config.enabled = true;
    await flushPromises();
    expect(fetchJoinable).toHaveBeenCalledTimes(1);

    streaming.joinableSessions = [
      {
        container: "http://box:3010",
        label: null,
        platform: "ps2",
        rom_id: 7,
        rom_name: "Game",
        host_username: "ana",
        claimed_at: null,
        platform_id: 1,
        platform_display_name: "PlayStation 2",
        path_cover_small: null,
        path_cover_large: null,
        url_cover: null,
      } satisfies JoinableSession,
    ];
    await flushPromises();

    expect(wrapper.text()).toContain("home.live-sessions");
    expect(wrapper.findAll("[data-test='live']")).toHaveLength(1);

    streaming.joinableSessions = [];
    await flushPromises();
    expect(wrapper.text()).not.toContain("home.live-sessions");
    wrapper.unmount();
  });

  it("does not render the empty state before the initial loads settle", async () => {
    stubHomeFetches(false);

    const wrapper = mountHome();

    expect(wrapper.text()).not.toContain("home.empty-headline");

    await flushPromises();

    expect(wrapper.text()).toContain("home.empty-headline");
  });
});
