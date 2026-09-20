import { describe, expect, it, vi } from "vitest";
import { nextTick, ref } from "vue";
import type { CoverResource, SearchCoverSchema } from "@/__generated__";
import { useCoverFilters } from "./index";

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

function resource(overrides: Partial<CoverResource> = {}): CoverResource {
  return {
    thumb: "https://cdn/thumb.png",
    url: "https://cdn/grid.png",
    type: "static",
    width: 600,
    height: 900,
    style: "",
    author: "",
    score: 0,
    nsfw: false,
    humor: false,
    epilepsy: false,
    ...overrides,
  };
}

const SGDB: SearchCoverSchema = {
  provider: "sgdb",
  name: "Blur",
  resources: [resource({ style: "alternate", author: "duckdicks", score: 4 })],
};
const STEAM: SearchCoverSchema = {
  provider: "steam",
  name: "Blur",
  resources: [resource({ url: "https://steam/header.jpg" })],
};

function setup(covers: SearchCoverSchema[]) {
  return useCoverFilters(ref(covers), ref([]));
}

describe("useCoverFilters providers", () => {
  it("shows every provider until one is toggled off", () => {
    const filters = setup([SGDB, STEAM]);

    expect(filters.filteredCovers.value.map((g) => g.provider)).toEqual([
      "sgdb",
      "steam",
    ]);

    filters.toggleProvider("steam");
    expect(filters.filteredCovers.value.map((g) => g.provider)).toEqual([
      "sgdb",
    ]);

    filters.resetFilters();
    expect(filters.filteredCovers.value).toHaveLength(2);
  });

  it("keeps the SteamGridDB-only controls off a Steam-only result set", () => {
    expect(setup([STEAM]).hasSgdbCovers.value).toBe(false);
    expect(setup([SGDB, STEAM]).hasSgdbCovers.value).toBe(true);
  });

  it("still counts hidden providers as raw results so the bar stays", () => {
    const filters = setup([STEAM]);
    filters.toggleProvider("steam");

    expect(filters.hasRawResults.value).toBe(true);
    expect(filters.hasResults.value).toBe(false);
  });
});

describe("useCoverFilters activeFilterCount", () => {
  it("counts only the filters moved off their defaults", () => {
    const filters = setup([SGDB]);
    expect(filters.activeFilterCount.value).toBe(0);

    filters.coverType.value = "animated";
    filters.showNsfw.value = true;
    filters.showHumor.value = false;
    filters.sortMode.value = "votes";
    expect(filters.activeFilterCount.value).toBe(3);

    filters.resetFilters();
    expect(filters.activeFilterCount.value).toBe(0);
  });

  it("skips the content switches while their controls are hidden", () => {
    const filters = setup([STEAM]);
    filters.showNsfw.value = true;

    expect(filters.activeFilterCount.value).toBe(0);
  });
});

describe("useCoverFilters new results", () => {
  it("drops a style picked from the previous results", async () => {
    const covers = ref([SGDB]);
    const filters = useCoverFilters(covers, ref([]));
    filters.styleFilter.value = "alternate";
    filters.showNsfw.value = true;

    covers.value = [STEAM];
    await nextTick();

    expect(filters.styleFilter.value).toBe("all");
    expect(filters.showNsfw.value).toBe(true);
    expect(filters.filteredCovers.value).toHaveLength(1);
  });
});
