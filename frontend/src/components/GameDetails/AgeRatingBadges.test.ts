import { RouterLinkStub, shallowMount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import { ROUTES } from "@/plugins/routeNames";
import { detailedRomFixture, romMetadataFixture } from "@/utils/rom.fixtures";
import AgeRatingBadges from "./AgeRatingBadges.vue";

function mount(ageRatings: string[], igdbRatings: [string, string][] = []) {
  const rom = detailedRomFixture({
    metadatum: romMetadataFixture({ age_ratings: ageRatings }),
    igdb_metadata: {
      age_ratings: igdbRatings.map(([category, rating]) => ({
        category,
        rating,
        rating_cover_url: `https://example.test/${category}_${rating}.png`,
      })),
    },
  });
  return shallowMount(AgeRatingBadges, {
    props: { rom },
    global: {
      stubs: { RouterLink: RouterLinkStub, RTooltip: false, RIcon: true },
    },
  });
}

function pivots(wrapper: ReturnType<typeof mount>) {
  return wrapper
    .findAllComponents(RouterLinkStub)
    .map((link) => link.props("to"));
}

describe("AgeRatingBadges", () => {
  it("pivots each badge to the ageRatings gallery search", () => {
    expect(pivots(mount(["ESRB:T", "PEGI:12"]))).toEqual([
      { name: ROUTES.SEARCH, query: { ageRatings: "ESRB:T" } },
      { name: ROUTES.SEARCH, query: { ageRatings: "PEGI:12" } },
    ]);
  });

  it("links a provider rating by its stored value, not the display label", () => {
    expect(pivots(mount(["12"], [["USK", "12"]]))).toEqual([
      { name: ROUTES.SEARCH, query: { ageRatings: "12" } },
    ]);
  });

  it("gives a rating shared by two categories one badge per category", () => {
    const wrapper = mount(
      ["12", "12"],
      [
        ["PEGI", "12"],
        ["USK", "12"],
      ],
    );

    const alts = wrapper.findAll("img").map((img) => img.attributes("alt"));
    expect(alts).toEqual(["PEGI: 12", "USK: 12"]);
  });

  it("renders nothing when the rom has no age ratings", () => {
    expect(pivots(mount([]))).toEqual([]);
  });
});
