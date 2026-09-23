import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import AssetTimestamp from "./AssetTimestamp.vue";

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ locale: "en_US" }),
}));

describe("AssetTimestamp", () => {
  it("shows the relative time over the exact moment", () => {
    const wrapper = mount(AssetTimestamp, {
      props: { date: "2026-09-16T12:00:00Z", align: "end" },
    });

    expect(wrapper.get(".r-asset-timestamp__relative").text()).not.toBe("");
    expect(wrapper.get(".r-asset-timestamp__exact").text()).toMatch(/2026/);
    expect(wrapper.classes()).toContain("r-asset-timestamp--end");
    expect(wrapper.classes()).not.toContain("r-asset-timestamp--inline");
  });

  it("sets the two side by side when inline", () => {
    const wrapper = mount(AssetTimestamp, {
      props: { date: "2026-09-16T12:00:00Z", inline: true },
    });

    expect(wrapper.classes()).toContain("r-asset-timestamp--inline");
  });
});
