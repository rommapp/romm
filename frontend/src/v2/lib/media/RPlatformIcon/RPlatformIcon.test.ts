import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import { nextTick } from "vue";
import { DEFAULT_PLATFORM_ICON } from "@/v2/composables/usePlatformIconCache/iconCache";
import RPlatformIcon from "./RPlatformIcon.vue";

vi.mock("@/v2/lib/structural/RTooltip/RTooltip.vue", () => ({
  default: { template: "<span><slot /></span>" },
}));

type Props = Partial<InstanceType<typeof RPlatformIcon>["$props"]>;

async function loadChain(props: Props): Promise<string[]> {
  const wrapper = mount(RPlatformIcon, {
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

describe("RPlatformIcon src", () => {
  it("uses the shipped file for the canonical slug", async () => {
    const wrapper = mount(RPlatformIcon, {
      props: { slug: "dc", fsSlug: "dreamcast", showTooltip: false },
    });

    expect(wrapper.find("img").attributes("src")).toBe(
      "/assets/platforms/dc.svg",
    );
    wrapper.unmount();
  });

  it("falls back to the filesystem slug when the canonical slug is unshipped", async () => {
    const wrapper = mount(RPlatformIcon, {
      props: { slug: "dreamcast", fsSlug: "dc", showTooltip: false },
    });

    expect(wrapper.find("img").attributes("src")).toBe(
      "/assets/platforms/dc.svg",
    );
    wrapper.unmount();
  });

  it("uses the default when nothing is shipped", async () => {
    const wrapper = mount(RPlatformIcon, {
      props: { fsSlug: "dreamcast", showTooltip: false },
    });

    expect(wrapper.find("img").attributes("src")).toBe(DEFAULT_PLATFORM_ICON);
    wrapper.unmount();
  });

  it("does not repeat a slug that already matches the folder name", async () => {
    const wrapper = mount(RPlatformIcon, {
      props: { slug: "nes", showTooltip: false },
    });

    expect(wrapper.find("img").attributes("src")).toBe(
      "/assets/platforms/nes.svg",
    );
    wrapper.unmount();
  });

  it("short-circuits to an explicit src", async () => {
    const wrapper = mount(RPlatformIcon, {
      props: { src: "/custom/icon.png", showTooltip: false },
    });

    expect(wrapper.find("img").attributes("src")).toBe("/custom/icon.png");
    wrapper.unmount();
  });

  it("falls back to the default when the resolved file fails to paint", async () => {
    await expect(loadChain({ slug: "dc" })).resolves.toEqual([
      "/assets/platforms/dc.svg",
      DEFAULT_PLATFORM_ICON,
    ]);
  });

  it("falls back to the default when an explicit src fails to paint", async () => {
    await expect(loadChain({ src: "/custom/icon.png" })).resolves.toEqual([
      "/custom/icon.png",
      DEFAULT_PLATFORM_ICON,
    ]);
  });
});
