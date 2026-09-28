import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import type { Facet, SimilarityReasonSchema } from "@/__generated__";
import RecommendationReason from "./RecommendationReason.vue";

// Renders the key plus anything interpolated, so an assertion can tell a
// tooltip that carries its game name from one that lost it.
vi.mock("vue-i18n", () => ({
  useI18n: () => ({
    t: (key: string, params?: unknown[]) =>
      [key, ...(params ?? [])].filter(Boolean).join(":"),
  }),
}));

const RIcon = {
  props: { icon: { type: String, default: "" } },
  template: `<i :data-icon="icon" />`,
};

function reason(facet: Facet, value = ""): SimilarityReasonSchema {
  return { facet, value };
}

function mountReason(props: {
  reasons: SimilarityReasonSchema[];
  seedRomName?: string | null;
}) {
  return mount(RecommendationReason, {
    props,
    global: { stubs: { RIcon } },
  });
}

describe("RecommendationReason", () => {
  it("captions the seed game ahead of any facet", () => {
    const wrapper = mountReason({
      reasons: [reason("franchise", "Metroid")],
      seedRomName: "Metroid Fusion",
    });

    expect(wrapper.find(".rec-reason__text").text()).toBe("Metroid Fusion");
    expect(wrapper.find("[data-icon]").attributes("data-icon")).toBe(
      "mdi-play",
    );
  });

  // The sentence is too wide for the cover, so the tooltip is the only place
  // it survives — an assertion on the caption text would not catch losing it.
  it("keeps the full sentence, with its game name, in the tooltip", () => {
    const wrapper = mountReason({ reasons: [], seedRomName: "Metroid Fusion" });

    expect(wrapper.find(".rec-reason").attributes("title")).toBe(
      "recommendations.because-you-played:Metroid Fusion",
    );
  });

  it("falls back to the first facet, with its own icon", () => {
    const wrapper = mountReason({
      reasons: [reason("genre", "Racing"), reason("decade", "1990")],
    });

    expect(wrapper.find(".rec-reason__text").text()).toBe("Racing");
    expect(wrapper.find("[data-icon]").attributes("data-icon")).toBe(
      "mdi-shape-outline",
    );
    expect(wrapper.find(".rec-reason").attributes("title")).toBe(
      "recommendations.why",
    );
  });

  it("renders nothing when the feed gives neither", () => {
    expect(mountReason({ reasons: [] }).find(".rec-reason").exists()).toBe(
      false,
    );
  });
});
