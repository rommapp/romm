import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import { nextTick } from "vue";
import PlatformIcon from "./PlatformIcon.vue";

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

describe("PlatformIcon source", () => {
  it("prefers the shipped svg for the canonical slug", async () => {
    await expect(
      loadChain({ slug: "dc", fsSlug: "dreamcast" }),
    ).resolves.toEqual([
      "/assets/platforms/dc.svg",
      "/assets/platforms/default.ico",
    ]);
  });

  it("uses the shipped ico when no svg ships", async () => {
    await expect(loadChain({ slug: "saturn" })).resolves.toEqual([
      "/assets/platforms/saturn.ico",
      "/assets/platforms/default.ico",
    ]);
  });

  it("falls back to the filesystem slug when the slug ships nothing", async () => {
    await expect(
      loadChain({ slug: "not-a-platform", fsSlug: "genesis" }),
    ).resolves.toEqual([
      "/assets/platforms/genesis.svg",
      "/assets/platforms/default.ico",
    ]);
  });

  it("goes straight to the default when nothing ships", async () => {
    await expect(
      loadChain({ slug: "not-a-platform", fsSlug: "also-not-one" }),
    ).resolves.toEqual(["/assets/platforms/default.ico"]);
  });

  it("matches slugs case-insensitively", async () => {
    await expect(loadChain({ name: "NES" })).resolves.toEqual([
      "/assets/platforms/nes.svg",
      "/assets/platforms/default.ico",
    ]);
  });

  it("uses an explicit src before the manifest", async () => {
    await expect(loadChain({ src: "/custom/icon.png" })).resolves.toEqual([
      "/custom/icon.png",
      "/assets/platforms/default.ico",
    ]);
  });
});

describe("PlatformIcon tooltip", () => {
  it("falls back to the slug when no title or alt is given", () => {
    const wrapper = mount(PlatformIcon, {
      props: { slug: "snes" },
      global: {
        stubs: { RTooltip: { props: ["text"], template: "<i>{{ text }}</i>" } },
      },
    });

    expect(wrapper.find("i").text()).toBe("snes");
  });
});
