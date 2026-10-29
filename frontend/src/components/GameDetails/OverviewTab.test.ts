import { shallowMount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ref } from "vue";
import type { IGDBRelatedGame, SimilarRomSchema } from "@/__generated__";
import { detailedRomFixture } from "@/utils/rom.fixtures";
import type { MediaShelfItem } from "./MediaShelf.vue";
import OverviewTab from "./OverviewTab.vue";

vi.mock("vue-i18n");

const showRecommendations = ref(true);
const similarGamesSource = ref("romm");

beforeEach(() => {
  showRecommendations.value = true;
  similarGamesSource.value = "romm";
});

vi.mock("@/composables/useUISettings", () => ({
  useUISettings: () => ({ showRecommendations, similarGamesSource }),
}));

vi.mock("@/stores/collections", () => ({
  default: () => ({ allCollections: [], smartCollections: [] }),
}));

vi.mock("@/composables/useWebpSupport", () => ({
  useWebpSupport: () => ({
    supportsWebp: ref(false),
    toWebp: (url: string) => url,
  }),
}));

const pinnedMedia = ref<MediaShelfItem[]>([]);
const isCustomized = ref(false);
const resetPins = vi.fn();

vi.mock("@/utils/pinnedMedia", () => ({
  resolvePinnedMedia: () => pinnedMedia.value,
}));

vi.mock("@/composables/usePinnedMedia", () => ({
  usePinnedMedia: () => ({
    canPin: ref(true),
    isPinned: ref(() => true),
    isCustomized,
    togglePin: vi.fn(),
    resetPins,
  }),
}));

vi.mock("@/utils/collectionCovers", () => ({
  collectionCoverList: () => [],
}));

function game(id: number, name: string): IGDBRelatedGame {
  return { id, name, slug: name, type: "port", cover_url: "" };
}

function similar(id: number): SimilarRomSchema {
  return {
    rom: { id, name: `Game ${id}` } as SimilarRomSchema["rom"],
    score: 0.5,
    reasons: [{ facet: "franchise", value: "Metroid" }],
  };
}

function mount(props: Record<string, unknown> = {}) {
  return shallowMount(OverviewTab, {
    props: {
      rom: detailedRomFixture({ id: 1 }),
      summary: null,
      sections: [],
      playerCount: null,
      userCollections: [],
      hltb: null,
      lastPlayed: null,
      revision: null,
      expansions: [],
      dlcs: [],
      remakes: [],
      remasters: [],
      ports: [],
      similarRoms: [],
      ...props,
    },
    global: { stubs: { RIcon: true, RBtn: false } },
  });
}

function gridItems(wrapper: ReturnType<typeof mount>) {
  return wrapper
    .findAllComponents({ name: "RelatedGamesGrid" })
    .map((c) => c.props("items") as IGDBRelatedGame[]);
}

describe("OverviewTab related games", () => {
  // IGDB has always sent `ports`; the overview dropped them on the floor.
  it("renders a grid for ports", () => {
    const ports = [game(7, "sonic-cd-pc")];
    expect(gridItems(mount({ ports }))).toEqual([ports]);
  });

  // `hasRelated` gates the whole block, so a ports-only game used to
  // render nothing at all.
  it("shows the related block when ports are the only related games", () => {
    expect(mount({ ports: [game(7, "a")] }).text()).toContain(
      "rom.related-ports",
    );
  });

  it("hides the ports section when there are none", () => {
    expect(mount({ remakes: [game(1, "a")] }).text()).not.toContain(
      "rom.related-ports",
    );
  });
});

describe("OverviewTab similar games", () => {
  const similarRoms = [similar(2), similar(3)];

  it("switches between RomM and IGDB using the saved source", async () => {
    const items = [game(8, "IGDB game")];
    const wrapper = mount({
      similarRoms,
      rom: detailedRomFixture({ igdb_metadata: { similar_games: items } }),
    });
    expect(
      wrapper.findComponent({ name: "SimilarGamesGrid" }).props("items"),
    ).toEqual(similarRoms);
    expect(gridItems(wrapper)).toEqual([]);
    await wrapper
      .findAll("button")
      .find((button) => button.text() === "IGDB")!
      .trigger("click");
    expect(similarGamesSource.value).toBe("igdb");
    expect(gridItems(wrapper)).toEqual([items]);
    expect(wrapper.findComponent({ name: "SimilarGamesGrid" }).exists()).toBe(
      false,
    );
    expect(
      gridItems(
        mount({
          rom: detailedRomFixture({ igdb_metadata: { similar_games: items } }),
        }),
      ),
    ).toEqual([items]);
  });

  it("keeps the selector reachable when the selected source is empty", () => {
    const wrapper = mount({
      rom: detailedRomFixture({
        igdb_metadata: { similar_games: [game(8, "IGDB game")] },
      }),
    });
    expect(wrapper.text()).toContain("common.no-results");
    expect(wrapper.text()).toContain("IGDB");
    similarGamesSource.value = "igdb";
    const empty = mount({ similarRoms });
    expect(empty.text()).toContain("common.no-results");
    expect(empty.text()).toContain("RomM");
  });

  it("hides both sources when recommendations are disabled", () => {
    showRecommendations.value = false;
    similarGamesSource.value = "igdb";
    const wrapper = mount({
      similarRoms,
      rom: detailedRomFixture({
        igdb_metadata: { similar_games: [game(8, "IGDB game")] },
      }),
    });
    expect(gridItems(wrapper)).toEqual([]);
    expect(wrapper.find('[role="group"]').exists()).toBe(false);
  });

  it("hides the section when neither source has games", () => {
    expect(mount().text()).not.toContain("recommendations.similar-games");
  });

  it("shows the section when recommendations are enabled", () => {
    showRecommendations.value = true;

    expect(
      mount({ similarRoms })
        .findComponent({ name: "SimilarGamesGrid" })
        .exists(),
    ).toBe(true);
  });

  it("hides the section when recommendations are turned off", () => {
    // The same preference hides the Home row; #3794 asked for the section to
    // be switchable off wherever it appears, not only on the home page.
    showRecommendations.value = false;

    expect(
      mount({ similarRoms })
        .findComponent({ name: "SimilarGamesGrid" })
        .exists(),
    ).toBe(false);
  });

  it("leaves the other related sections alone when it is off", () => {
    // The preference gates recommendations, not expansions and remakes, and
    // those share the panel whose visibility the gate feeds into.
    showRecommendations.value = false;
    const wrapper = mount({
      similarRoms,
      expansions: [{ id: 9, name: "Eagle Watch" }],
    });

    expect(wrapper.findComponent({ name: "SimilarGamesGrid" }).exists()).toBe(
      false,
    );
    expect(wrapper.findComponent({ name: "RelatedGamesGrid" }).exists()).toBe(
      true,
    );
  });
});

describe("OverviewTab media", () => {
  const shot: MediaShelfItem = { key: "file:1", label: "Shot", url: "/a.png" };

  it("shows the pinned media without a reset while on the defaults", () => {
    pinnedMedia.value = [shot];
    isCustomized.value = false;
    const wrapper = mount();

    const shelf = wrapper.findComponent({ name: "MediaShelf" });
    expect(shelf.props("items")).toEqual([shot]);
    expect(wrapper.text()).not.toContain("rom.pinned-media-reset");
  });

  it("hides the section when the defaults hold nothing", () => {
    pinnedMedia.value = [];
    isCustomized.value = false;

    expect(mount().text()).not.toContain("rom.media");
  });

  it("keeps the reset reachable after unpinning everything", async () => {
    pinnedMedia.value = [];
    isCustomized.value = true;
    const wrapper = mount();

    expect(wrapper.text()).toContain("rom.pinned-media-empty");
    await wrapper.find("button").trigger("click");
    expect(resetPins).toHaveBeenCalled();
  });
});
