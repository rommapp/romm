import { shallowMount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { IGDBRelatedGame, RomMetadataSchema } from "@/__generated__";
import type { DetailedRom } from "@/stores/roms";
import OverviewTab from "./OverviewTab.vue";

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

const EMPTY_METADATA: RomMetadataSchema = {
  rom_id: 1,
  genres: [],
  franchises: [],
  collections: [],
  companies: [],
  publishers: [],
  developers: [],
  game_modes: [],
  age_ratings: [],
  player_count: "",
  first_release_date: null,
  average_rating: null,
};

function game(id: number, name: string): IGDBRelatedGame {
  return { id, name, slug: name, type: "port", cover_url: "" };
}

function rom(overrides: Partial<DetailedRom> = {}): DetailedRom {
  return {
    id: 1,
    metadatum: EMPTY_METADATA,
    files: [],
    user_screenshots: [],
    ...overrides,
  } as DetailedRom;
}

type RelatedOverrides = Partial<{
  expansions: IGDBRelatedGame[];
  dlcs: IGDBRelatedGame[];
  remakes: IGDBRelatedGame[];
  remasters: IGDBRelatedGame[];
  ports: IGDBRelatedGame[];
  similarGames: IGDBRelatedGame[];
}>;

function mountTab(related: RelatedOverrides = {}) {
  return shallowMount(OverviewTab, {
    props: {
      rom: rom(),
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
      similarGames: [],
      ...related,
    },
  });
}

function gridItems(wrapper: ReturnType<typeof mountTab>) {
  return wrapper
    .findAllComponents({ name: "RelatedGamesGrid" })
    .map((c) => c.props("items") as IGDBRelatedGame[]);
}

describe("OverviewTab related games", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
  });

  // IGDB has always sent `ports`; the overview dropped them on the floor.
  it("renders a grid for ports", () => {
    const ports = [game(7, "sonic-cd-pc")];
    expect(gridItems(mountTab({ ports }))).toEqual([ports]);
  });

  // `hasRelated` gates the whole block, so a ports-only game used to
  // render nothing at all.
  it("shows the related block when ports are the only related games", () => {
    expect(mountTab({ ports: [game(7, "a")] }).text()).toContain(
      "rom.related-ports",
    );
  });

  it("hides the ports section when there are none", () => {
    expect(mountTab({ remakes: [game(1, "a")] }).text()).not.toContain(
      "rom.related-ports",
    );
  });
});
