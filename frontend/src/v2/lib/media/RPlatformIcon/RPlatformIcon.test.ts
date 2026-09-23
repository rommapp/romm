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
    props: { src: "/custom/icon.png", showTooltip: false, ...props },
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

describe("RPlatformIcon", () => {
  it("renders the given src", () => {
    const wrapper = mount(RPlatformIcon, {
      props: { src: "/custom/icon.png", showTooltip: false },
    });

    expect(wrapper.find("img").attributes("src")).toBe("/custom/icon.png");
    wrapper.unmount();
  });

  it("falls back when src fails to paint", async () => {
    await expect(
      loadChain({
        src: "/custom/icon.png",
        fallbackSrc: "/assets/platforms/default.ico",
      }),
    ).resolves.toEqual(["/custom/icon.png", "/assets/platforms/default.ico"]);
  });

  it("stays on src when no fallback is set", async () => {
    await expect(loadChain({ src: "/custom/icon.png" })).resolves.toEqual([
      "/custom/icon.png",
    ]);
  });
});
