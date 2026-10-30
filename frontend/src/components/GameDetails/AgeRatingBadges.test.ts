import { RouterLinkStub, shallowMount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import type { DetailedRom } from "@/stores/roms";
import { detailedRomFixture, romMetadataFixture } from "@/utils/rom.fixtures";
import AgeRatingBadges from "./AgeRatingBadges.vue";

vi.mock("vue-i18n");

vi.mock("@/utils/searchLocation", () => ({
  searchLocation: (filter: string, value: string) => ({
    name: "search",
    query: { [filter]: value },
  }),
}));

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
      name: "search",
      query: { ageRatings: "ESRB:T" },
    });
    expect(links[1]!.props("to")).toEqual({
      name: "search",
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
      name: "search",
      query: { ageRatings: "12" },
    });
  });

  it("renders nothing when the rom has no age ratings", () => {
    const wrapper = shallowMount(AgeRatingBadges, {
      props: { rom: rom([]) },
      global: { stubs },
    });

    expect(wrapper.findAllComponents(RouterLinkStub)).toHaveLength(0);
  });
});
