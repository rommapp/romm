import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import AssetTimestamp from "./AssetTimestamp.vue";

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ locale: "en_US" }),
}));

describe("AssetTimestamp", () => {
  it("shows the relative time and the exact moment", () => {
    const wrapper = mount(AssetTimestamp, {
      props: { date: "2026-09-16T12:00:00Z", stacked: true },
    });

    expect(wrapper.get(".r-asset-timestamp__relative").text()).not.toBe("");
    expect(wrapper.get(".r-asset-timestamp__exact").text()).toMatch(/2026/);
    expect(wrapper.classes()).toContain("r-asset-timestamp--stacked");
  });
});
