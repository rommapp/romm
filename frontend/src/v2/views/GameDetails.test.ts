import { flushPromises, mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import { defineComponent, type Ref, ref } from "vue";
import type { RAGameRomAchievement } from "@/__generated__";
import type { DetailedRom } from "@/stores/roms";
import { saveFixture, stateFixture } from "@/utils/assets.fixtures";
import { detailedRomFixture } from "@/utils/rom.fixtures";
import { channelFixture } from "@/v2/utils/snapshots.fixtures";
import GameDetails from "./GameDetails.vue";

const { route, routeRom, panel } = vi.hoisted(() => ({
  route: { query: {} as Record<string, string>, params: { rom: "1" } },
  // The mocked module fills this with the ref the view reads its ROM from.
  routeRom: { current: null as Ref<DetailedRom | null> | null },
  // Each tab panel renders a marker, so a test can tell which one is open.
  panel: (name: string) => ({
    default: { template: `<div data-test="panel-${name}" />` },
  }),
}));

vi.mock("vue-i18n");

vi.mock("vue-router", () => ({
  useRoute: () => route,
  useRouter: () => ({
    currentRoute: { value: { path: "/rom/1", query: route.query } },
    replace: vi.fn(),
  }),
  onBeforeRouteUpdate: vi.fn(),
  isNavigationFailure: () => false,
  NavigationFailureType: {},
}));

vi.mock("@/v2/composables/useRouteRom", async () => {
  const { ref: vueRef } = await import("vue");
  routeRom.current = vueRef<DetailedRom | null>(null);
  return {
    useRouteRom: () => routeRom.current,
    romIdFromRoute: () => 1,
  };
});

vi.mock("@/services/api/rom", () => ({
  default: { getSimilarRoms: vi.fn(() => new Promise(() => {})) },
}));
vi.mock("@/services/pending-asset", () => ({
  pendingAssetKinds: vi.fn(() => Promise.resolve(new Set())),
}));
vi.mock("@/stores/streaming", () => ({
  useStreamingStore: () => ({ fetchJoinableSessions: vi.fn() }),
}));
vi.mock("@/composables/useUISettings", () => ({
  useUISettings: () => ({ showRecommendations: ref(false) }),
}));
vi.mock("@/v2/composables/useBackgroundArt", () => ({
  useBackgroundArt: () => vi.fn(),
}));
vi.mock("@/v2/composables/useBreakpoint", () => ({
  useBreakpoint: () => ({ smAndDown: ref(false) }),
}));
vi.mock("@/v2/composables/useRightStickScroll", () => ({
  useRightStickScroll: vi.fn(),
}));
vi.mock("@/v2/composables/useRomScanRefresh", () => ({
  useRomScanRefresh: vi.fn(),
}));
vi.mock("@/v2/composables/useSnackbar", () => ({
  useSnackbar: () => ({ warning: vi.fn() }),
}));
vi.mock("@/v2/composables/usePageTitle", () => ({ usePageTitle: vi.fn() }));

vi.mock("@v2/lib", () => ({
  RTabNav: defineComponent({
    props: {
      modelValue: { type: String, default: "" },
      items: { type: Array, default: () => [] },
    },
    template: `<nav data-test="tabs" :data-active="modelValue">
      <span v-for="item in items" :key="item.id" data-test="tab" :data-badge="item.badge">{{ item.id }}</span>
    </nav>`,
  }),
}));

vi.mock("@/v2/components/GameDetails/AchievementsTab.vue", () =>
  panel("achievements"),
);
vi.mock("@/v2/components/GameDetails/CoverColumn.vue", () => panel("cover"));
vi.mock("@/v2/components/GameDetails/FilesTab/FilesTab.vue", () =>
  panel("files"),
);
vi.mock("@/v2/components/GameDetails/GameHeader.vue", () => panel("header"));
vi.mock("@/v2/components/GameDetails/MediaTab.vue", () => panel("media"));
vi.mock("@/v2/components/GameDetails/MetadataTab.vue", () => panel("metadata"));
vi.mock("@/v2/components/GameDetails/NotesTab.vue", () => panel("notes"));
vi.mock("@/v2/components/GameDetails/OverviewTab.vue", () => panel("overview"));
vi.mock("@/v2/components/GameDetails/PatcherTab.vue", () => panel("patcher"));
vi.mock("@/v2/components/GameDetails/PrevNextNav.vue", () =>
  panel("prev-next"),
);
vi.mock("@/v2/components/GameDetails/SaveDataTab.vue", () =>
  panel("save-data"),
);

const achievement: RAGameRomAchievement = {
  ra_id: 1,
  title: "First",
  description: null,
  points: 5,
  num_awarded: null,
  num_awarded_hardcore: null,
  badge_id: "1",
  badge_url_lock: null,
  badge_path_lock: null,
  badge_url: null,
  badge_path: null,
  display_order: 1,
  type: null,
};

function romWith(achievements: RAGameRomAchievement[] | null): DetailedRom {
  return detailedRomFixture({
    ra_id: achievements ? 10210 : null,
    merged_ra_metadata: achievements ? { achievements } : null,
  });
}

function showRom(rom: DetailedRom) {
  if (!routeRom.current) throw new Error("useRouteRom mock not loaded");
  routeRom.current.value = rom;
}

async function mountDetails(rom: DetailedRom, tab?: string) {
  route.query = tab ? { tab } : {};
  showRom(rom);
  const wrapper = mount(GameDetails);
  await flushPromises();
  return wrapper;
}

const tabIds = (wrapper: Awaited<ReturnType<typeof mountDetails>>) =>
  wrapper.findAll('[data-test="tab"]').map((tab) => tab.text());

describe("GameDetails save data badge", () => {
  it("counts backups and own channels, not the rows channels hold", async () => {
    const wrapper = await mountDetails(
      detailedRomFixture({
        user_saves: [
          saveFixture({ id: 1 }),
          saveFixture({ id: 2, channel_id: "c1", slot: "autosave" }),
          saveFixture({ id: 3, channel_id: "c1" }),
        ],
        user_states: [
          stateFixture({ id: 4 }),
          stateFixture({ id: 5, channel_id: "c1" }),
        ],
        user_channels: [
          channelFixture({ id: "c1" }),
          channelFixture({ id: "c2", is_own: false }),
        ],
      }),
    );

    const badge = wrapper
      .findAll('[data-test="tab"]')
      .find((tab) => tab.text() === "save-data")
      ?.attributes("data-badge");
    expect(badge).toBe("3");
  });
});

describe("GameDetails achievements tab", () => {
  it("offers the tab when the ROM has achievements", async () => {
    const wrapper = await mountDetails(romWith([achievement]));

    expect(tabIds(wrapper)).toContain("achievements");
  });

  it.each([
    ["no RA match", null],
    ["an RA game with no set", []],
  ])("hides the tab for %s", async (_label, achievements) => {
    const wrapper = await mountDetails(romWith(achievements));

    expect(tabIds(wrapper)).not.toContain("achievements");
  });

  it("opens the overview for a ?tab= the ROM has no tab for", async () => {
    const wrapper = await mountDetails(romWith(null), "achievements");

    expect(wrapper.find('[data-test="tabs"]').attributes("data-active")).toBe(
      "overview",
    );
    expect(wrapper.find('[data-test="panel-overview"]').exists()).toBe(true);
    expect(wrapper.find('[data-test="panel-achievements"]').exists()).toBe(
      false,
    );
  });

  it("reopens the achievements panel when the next ROM has a set", async () => {
    const wrapper = await mountDetails(romWith(null), "achievements");

    showRom(romWith([achievement]));
    await flushPromises();

    expect(tabIds(wrapper)).toContain("achievements");
    expect(wrapper.find('[data-test="panel-achievements"]').exists()).toBe(
      true,
    );
  });

  it("opens the achievements panel from ?tab= when the ROM has a set", async () => {
    const wrapper = await mountDetails(romWith([achievement]), "achievements");

    expect(wrapper.find('[data-test="panel-achievements"]').exists()).toBe(
      true,
    );
  });
});
