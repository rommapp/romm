import { RouterLinkStub, shallowMount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import { ROUTES } from "@/plugins/routeNames";
import type { DetailedRom } from "@/stores/roms";
import { detailedRomFixture, romMetadataFixture } from "@/utils/rom.fixtures";
import AgeRatingBadges from "./AgeRatingBadges.vue";

function rom(ageRatings: string[]): DetailedRom {
  return detailedRomFixture({
    metadatum: romMetadataFixture({ age_ratings: ageRatings }),
  });
}

const stubs = { RouterLink: RouterLinkStub, RTooltip: false, RIcon: true };

describe("AgeRatingBadges", () => {
  it("pivots each badge to the ageRatings gallery search", () => {
    const wrapper = shallowMount(AgeRatingBadges, {
      props: { rom: rom(["ESRB:T", "PEGI:12"]) },
      global: { stubs },
    });

    const links = wrapper.findAllComponents(RouterLinkStub);
    expect(links).toHaveLength(2);
    expect(links[0]!.props("to")).toEqual({
      name: ROUTES.SEARCH,
      query: { ageRatings: "ESRB:T" },
    });
    expect(links[1]!.props("to")).toEqual({
      name: ROUTES.SEARCH,
      query: { ageRatings: "PEGI:12" },
    });
  });

  it("links a provider rating by its stored value, not the display label", () => {
    const wrapper = shallowMount(AgeRatingBadges, {
      props: {
        rom: detailedRomFixture({
          metadatum: romMetadataFixture({ age_ratings: ["12"] }),
          igdb_metadata: {
            age_ratings: [
              {
                category: "USK",
                rating: "12",
                rating_cover_url: "https://example.test/usk_12.png",
              },
            ],
          },
        }),
      },
      global: { stubs },
    });

    const link = wrapper.findComponent(RouterLinkStub);
    expect(link.props("to")).toEqual({
      name: ROUTES.SEARCH,
      query: { ageRatings: "12" },
    });
  });

  it("gives a rating shared by two categories one badge per category", () => {
    const wrapper = shallowMount(AgeRatingBadges, {
      props: {
        rom: detailedRomFixture({
          metadatum: romMetadataFixture({ age_ratings: ["12", "12"] }),
          igdb_metadata: {
            age_ratings: [
              {
                category: "PEGI",
                rating: "12",
                rating_cover_url: "https://example.test/pegi_12.png",
              },
              {
                category: "USK",
                rating: "12",
                rating_cover_url: "https://example.test/usk_12.png",
              },
            ],
          },
        }),
      },
      global: { stubs },
    });

    const alts = wrapper.findAll("img").map((img) => img.attributes("alt"));
    expect(alts).toEqual(["PEGI: 12", "USK: 12"]);
  });

  it("renders nothing when the rom has no age ratings", () => {
    const wrapper = shallowMount(AgeRatingBadges, {
      props: { rom: rom([]) },
      global: { stubs },
    });

    expect(wrapper.findAllComponents(RouterLinkStub)).toHaveLength(0);
  });
});
