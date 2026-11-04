import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import CachedPlatformIcon from "./CachedPlatformIcon.vue";

describe("CachedPlatformIcon", () => {
  it("uses the shipped icon, then the default when it fails to load", async () => {
    const wrapper = mount(CachedPlatformIcon, { props: { slug: "saturn" } });
    expect(wrapper.find("img").attributes("src")).toBe(
      "/assets/platforms/saturn.ico",
    );

    await wrapper.find("img").trigger("error");

    expect(wrapper.find("img").attributes("src")).toBe(
      "/assets/platforms/default.ico",
    );
  });

  it("goes straight to the default when nothing ships", () => {
    const wrapper = mount(CachedPlatformIcon, {
      props: { slug: "not-a-platform" },
    });

    expect(wrapper.find("img").attributes("src")).toBe(
      "/assets/platforms/default.ico",
    );
  });
});
