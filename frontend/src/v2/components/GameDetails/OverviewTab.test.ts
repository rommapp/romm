import { shallowMount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import { ref } from "vue";
import type { IGDBRelatedGame, SimilarRomSchema } from "@/__generated__";
import type { DetailedRom } from "@/stores/roms";
import OverviewTab from "./OverviewTab.vue";

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

const showRecommendations = ref(true);

vi.mock("@/composables/useUISettings", () => ({
  useUISettings: () => ({ showRecommendations }),
}));

vi.mock("@/stores/collections", () => ({
  default: () => ({ allCollections: [], smartCollections: [] }),
}));

vi.mock("@/v2/composables/useWebpSupport", () => ({
  useWebpSupport: () => ({
    supportsWebp: ref(false),
    toWebp: (url: string) => url,
  }),
}));

// Artwork and collection mosaics belong to other sections; stubbed so this
// stays a test of the related-games block.
vi.mock("@/v2/utils/romArtwork", () => ({ resolveRomArtwork: () => [] }));

vi.mock("@/v2/utils/collectionCovers", () => ({
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
      rom: { id: 1, metadatum: {} } as DetailedRom,
      summary: null,
      sections: [],
      playerCount: null,
      userCollections: [],
      hltb: null,
      lastPlayed: null,
      revision: null,
      screenshots: [],
      expansions: [],
      dlcs: [],
      remakes: [],
      remasters: [],
      ports: [],
      similarRoms: [],
      ...props,
    },
    global: { stubs: { RIcon: true } },
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
