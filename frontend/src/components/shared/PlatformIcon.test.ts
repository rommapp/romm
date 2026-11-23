import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import { nextTick } from "vue";
import {
  DEFAULT_PLATFORM_ICON,
  shippedPlatformIconUrl,
} from "@/utils/platformIcons";
import PlatformIcon from "./PlatformIcon.vue";

type Props = Partial<InstanceType<typeof PlatformIcon>["$props"]>;

/** The src before and after one load error, collapsed when unchanged. */
async function loadChain(props: Props): Promise<string[]> {
  const wrapper = mount(PlatformIcon, {
    props: { showTooltip: false, ...props },
  });
  const first = wrapper.find("img").attributes("src");
  await wrapper.find("img").trigger("error");
  await nextTick();
  const second = wrapper.find("img").attributes("src");
  wrapper.unmount();
  return [...new Set([first, second])].filter((src) => src !== undefined);
}

describe("PlatformIcon source", () => {
  it("prefers the shipped svg for the canonical slug", async () => {
    await expect(
      loadChain({ slug: "dc", fsSlug: "dreamcast" }),
    ).resolves.toEqual([
      "/assets/platforms/dc.svg",
      "/assets/platforms/default.svg",
    ]);
  });

  it("uses the shipped ico when no svg ships", async () => {
    await expect(loadChain({ slug: "saturn" })).resolves.toEqual([
      "/assets/platforms/saturn.ico",
      "/assets/platforms/default.svg",
    ]);
  });

  it("falls back to the filesystem slug when the slug ships nothing", async () => {
    await expect(
      loadChain({ slug: "not-a-platform", fsSlug: "genesis" }),
    ).resolves.toEqual([
      "/assets/platforms/genesis.svg",
      "/assets/platforms/default.svg",
    ]);
  });

  it("goes straight to the default when nothing ships", async () => {
    await expect(
      loadChain({ slug: "not-a-platform", fsSlug: "also-not-one" }),
    ).resolves.toEqual(["/assets/platforms/default.svg"]);
  });

  it("resolves the default slug and the fallback constant to the svg", () => {
    expect(DEFAULT_PLATFORM_ICON).toBe("/assets/platforms/default.svg");
    expect(shippedPlatformIconUrl("default")).toBe(
      "/assets/platforms/default.svg",
    );
  });

  it("matches slugs case-insensitively", async () => {
    await expect(loadChain({ name: "NES" })).resolves.toEqual([
      "/assets/platforms/nes.svg",
      "/assets/platforms/default.svg",
    ]);
  });

  it("uses an explicit src before the manifest", async () => {
    await expect(loadChain({ src: "/custom/icon.png" })).resolves.toEqual([
      "/custom/icon.png",
      "/assets/platforms/default.svg",
    ]);
  });
});

describe("PlatformIcon load failure", () => {
  it("gives a new source a fresh try", async () => {
    const wrapper = mount(PlatformIcon, {
      props: { showTooltip: false, src: "/a.png" },
    });
    await wrapper.find("img").trigger("error");
    expect(wrapper.find("img").attributes("src")).toBe(
      "/assets/platforms/default.svg",
    );

    await wrapper.setProps({ src: "/b.png" });
    expect(wrapper.find("img").attributes("src")).toBe("/b.png");
    wrapper.unmount();
  });
});
