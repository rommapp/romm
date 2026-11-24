import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import MetricMenuButton from "./MetricMenuButton.vue";

function mountBtn() {
  return mount(MetricMenuButton, {
    props: {
      value: 0,
      label: "Difficulty",
      iconFull: "mdi-hand-back-right",
      iconEmpty: "mdi-hand-back-right-outline",
      accent: "brand-primary",
    },
    global: { stubs: { RIcon: true, RTooltip: true, MetricSection: true } },
  });
}

describe("MetricMenuButton", () => {
  it("names the metric in a hover tooltip", () => {
    const wrapper = mountBtn();

    const tooltip = wrapper.findComponent({ name: "RTooltip" });

    expect(tooltip.props("text")).toBe("Difficulty");
  });
});
