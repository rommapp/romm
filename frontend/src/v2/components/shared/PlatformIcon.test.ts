import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import { nextTick } from "vue";
import { DEFAULT_PLATFORM_ICON } from "@/v2/composables/usePlatformIconCache/iconCache";
import PlatformIcon from "./PlatformIcon.vue";

vi.mock("@/v2/lib/structural/RTooltip/RTooltip.vue", () => ({
  default: { template: "<span><slot /></span>" },
}));

type Props = Partial<InstanceType<typeof PlatformIcon>["$props"]>;

async function loadChain(props: Props): Promise<string[]> {
  const wrapper = mount(PlatformIcon, {
    props: { showTooltip: false, ...props },
  });

  const seen: string[] = [];
  for (let step = 0; step < 8; step += 1) {
    const img = wrapper.find("img");
    if (!img.exists()) break;
    const src = img.attributes("src");
    if (!src || seen[seen.length - 1] === src) break;
    seen.push(src);
    await img.trigger("error");
    await nextTick();
  }
  wrapper.unmount();
  return seen;
}

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

  it("falls back to the default when an explicit src fails to paint", async () => {
    await expect(loadChain({ src: "/custom/icon.png" })).resolves.toEqual([
      "/custom/icon.png",
      DEFAULT_PLATFORM_ICON,
    ]);
  });

  it("stays on src when already showing the default", async () => {
    await expect(loadChain({ fsSlug: "dreamcast" })).resolves.toEqual([
      DEFAULT_PLATFORM_ICON,
    ]);
  });
});
