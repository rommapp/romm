import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { defineComponent, ref } from "vue";
import type { RAGameRomAchievement } from "@/__generated__";
import type { DetailedRom } from "@/stores/roms";
import { makeDetailedRom } from "@/utils/rom.fixtures";
import GameDetails from "./GameDetails.vue";

const { route, currentRom, panel } = vi.hoisted(() => ({
  route: { query: {} as Record<string, string>, params: { rom: "1" } },
  currentRom: { value: null as DetailedRom | null },
  // Each tab panel renders a marker, so a test can tell which one is open.
  panel: (name: string) => ({
    default: { template: `<div data-test="panel-${name}" />` },
  }),
}));

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key, locale: { value: "en_US" } }),
}));

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
  const rom = vueRef<DetailedRom | null>(null);
  return {
    useRouteRom: () => {
      rom.value = currentRom.value;
      return rom;
    },
    romIdFromRoute: () => 1,
  };
});

vi.mock("@/services/api/rom", () => ({
  default: { getSimilarRoms: vi.fn(() => new Promise(() => {})) },
}));
vi.mock("@/services/pending-asset", () => ({
  pendingAssetKinds: vi.fn(async () => new Set()),
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
      <span v-for="item in items" :key="item.id" data-test="tab">{{ item.id }}</span>
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

const achievement = { ra_id: 1, title: "First" } as RAGameRomAchievement;

function romWith(achievements: RAGameRomAchievement[] | null): DetailedRom {
  return makeDetailedRom({
    ra_id: achievements ? 10210 : null,
    merged_ra_metadata: achievements ? { achievements } : null,
  });
}

async function mountDetails(rom: DetailedRom, tab?: string) {
  route.query = tab ? { tab } : {};
  currentRom.value = rom;
  const wrapper = mount(GameDetails);
  await flushPromises();
  return wrapper;
}

const tabIds = (wrapper: Awaited<ReturnType<typeof mountDetails>>) =>
  wrapper.findAll('[data-test="tab"]').map((tab) => tab.text());

describe("GameDetails achievements tab", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
  });

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

  it("opens the achievements panel from ?tab= when the ROM has a set", async () => {
    const wrapper = await mountDetails(romWith([achievement]), "achievements");

    expect(wrapper.find('[data-test="panel-achievements"]').exists()).toBe(
      true,
    );
  });
});
