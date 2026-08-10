import { shallowMount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { IGDBRelatedGame } from "@/__generated__";
import type { DetailedRom } from "@/stores/roms";
import OverviewTab from "./OverviewTab.vue";

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

function game(id: number, name: string): IGDBRelatedGame {
  return { id, name, slug: name, type: "port", cover_url: "" };
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
      rom: {
        id: 1,
        metadatum: null,
        files: [],
        user_screenshots: [],
      } as DetailedRom,
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
