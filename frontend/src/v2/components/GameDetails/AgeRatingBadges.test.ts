import { shallowMount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import type { DetailedRom } from "@/stores/roms";
import AgeRatingBadges from "./AgeRatingBadges.vue";

vi.mock("vue-i18n");

vi.mock("@/v2/utils/searchLocation", () => ({
  searchLocation: (filter: string, value: string) => ({
    name: "search",
    query: { [filter]: value },
  }),
}));

function rom(ageRatings: string[]): DetailedRom {
  return {
    id: 1,
    metadatum: { age_ratings: ageRatings },
  } as unknown as DetailedRom;
}

describe("AgeRatingBadges", () => {
  it("pivots each badge to the ageRatings gallery search", () => {
    const wrapper = shallowMount(AgeRatingBadges, {
      props: { rom: rom(["ESRB:T", "PEGI:12"]) },
      global: { stubs: { RTooltip: false, RIcon: true } },
    });

    const links = wrapper.findAll("router-link-stub");
    expect(links).toHaveLength(2);
    expect(links[0]!.attributes("to")).toEqual(
      JSON.stringify({ name: "search", query: { ageRatings: "ESRB:T" } }),
    );
    expect(links[1]!.attributes("to")).toEqual(
      JSON.stringify({ name: "search", query: { ageRatings: "PEGI:12" } }),
    );
  });

  it("links the stored entry, not the reconstructed display label", () => {
    const wrapper = shallowMount(AgeRatingBadges, {
      props: {
        rom: {
          id: 1,
          metadatum: { age_ratings: ["USK:12"] },
          igdb_metadata: {
            age_ratings: [
              {
                category: "USK",
                rating: "12",
                rating_cover_url: "https://example.test/usk.png",
              },
            ],
          },
        } as unknown as DetailedRom,
      },
      global: { stubs: { RTooltip: false, RIcon: true } },
    });

    const link = wrapper.find("router-link-stub");
    expect(link.attributes("to")).toEqual(
      JSON.stringify({ name: "search", query: { ageRatings: "USK:12" } }),
    );
  });

  it("renders nothing when the rom has no age ratings", () => {
    const wrapper = shallowMount(AgeRatingBadges, {
      props: { rom: rom([]) },
      global: { stubs: { RTooltip: false, RIcon: true } },
    });

    expect(wrapper.findAll("router-link-stub")).toHaveLength(0);
  });
});
