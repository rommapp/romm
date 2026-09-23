import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import { DEFAULT_PLATFORM_ICON } from "@/v2/composables/usePlatformIconCache/iconCache";
import PlatformIcon from "./PlatformIcon.vue";

vi.mock("@/v2/lib/structural/RTooltip/RTooltip.vue", () => ({
  default: { template: "<span><slot /></span>" },
}));

describe("PlatformIcon", () => {
  it("uses the shipped file for the canonical slug", () => {
    const wrapper = mount(PlatformIcon, {
      props: { slug: "dc", fsSlug: "dreamcast", showTooltip: false },
    });

    expect(wrapper.find("img").attributes("src")).toBe(
      "/assets/platforms/dc.svg",
    );
    wrapper.unmount();
  });

  it("falls back to the filesystem slug when the canonical slug is unshipped", () => {
    const wrapper = mount(PlatformIcon, {
      props: { slug: "dreamcast", fsSlug: "dc", showTooltip: false },
    });

    expect(wrapper.find("img").attributes("src")).toBe(
      "/assets/platforms/dc.svg",
    );
    wrapper.unmount();
  });

  it("uses the default when nothing is shipped", () => {
    const wrapper = mount(PlatformIcon, {
      props: { fsSlug: "dreamcast", showTooltip: false },
    });

    expect(wrapper.find("img").attributes("src")).toBe(DEFAULT_PLATFORM_ICON);
    wrapper.unmount();
  });

  it("short-circuits to an explicit src", () => {
    const wrapper = mount(PlatformIcon, {
      props: { src: "/custom/icon.png", showTooltip: false },
    });

    expect(wrapper.find("img").attributes("src")).toBe("/custom/icon.png");
    wrapper.unmount();
  });
});
