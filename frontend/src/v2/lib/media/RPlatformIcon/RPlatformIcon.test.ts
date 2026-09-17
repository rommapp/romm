import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import { nextTick } from "vue";
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

describe("RPlatformIcon candidate chain", () => {
  it("probes the canonical slug before the filesystem folder name", async () => {
    await expect(
      loadChain({ slug: "dc", fsSlug: "dreamcast" }),
    ).resolves.toEqual([
      "/assets/platforms/dc.svg",
      "/assets/platforms/dc.ico",
      "/assets/platforms/dreamcast.svg",
      "/assets/platforms/dreamcast.ico",
      "/assets/platforms/default.ico",
    ]);
  });

  it("uses the filesystem slug alone when no slug is given", async () => {
    await expect(loadChain({ fsSlug: "dreamcast" })).resolves.toEqual([
      "/assets/platforms/dreamcast.svg",
      "/assets/platforms/dreamcast.ico",
      "/assets/platforms/default.ico",
    ]);
  });

  it("does not repeat a slug that already matches the folder name", async () => {
    await expect(loadChain({ slug: "nes" })).resolves.toEqual([
      "/assets/platforms/nes.svg",
      "/assets/platforms/nes.ico",
      "/assets/platforms/default.ico",
    ]);
  });

  it("still reads the fsSlug prop as a fallback for slug", async () => {
    await expect(
      loadChain({ name: "genesis", fsSlug: "megadrive" }),
    ).resolves.toEqual([
      "/assets/platforms/genesis.svg",
      "/assets/platforms/genesis.ico",
      "/assets/platforms/megadrive.svg",
      "/assets/platforms/megadrive.ico",
      "/assets/platforms/default.ico",
    ]);
  });

  it("short-circuits to an explicit src", async () => {
    await expect(loadChain({ src: "/custom/icon.png" })).resolves.toEqual([
      "/custom/icon.png",
    ]);
  });
});
