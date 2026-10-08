import { mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { nextTick, type Ref } from "vue";
import { romFixture } from "@/utils/rom.fixtures";
import GameCover from "./GameCover.vue";

const { animation } = vi.hoisted(() => ({
  animation: { active: null as Ref<boolean> | null },
}));

vi.mock("@/v2/composables/useCoverAnimation", () => ({
  useCoverAnimation: (opts: { active: Ref<boolean> }) => {
    animation.active = opts.active;
    return { isVideoPlaying: { value: false }, playLoad: () => 0 };
  },
}));

describe("GameCover hover", () => {
  beforeEach(() => {
    animation.active = null;
  });

  it("animates while hovered when hoverMotion is set", async () => {
    const wrapper = mount(GameCover, {
      props: { rom: null, title: "Hollow Knight", hoverMotion: true },
    });
    // Listeners bind once the root element ref lands, a tick after mount.
    await nextTick();

    await wrapper.trigger("mouseenter");
    expect(animation.active?.value).toBe(true);

    await wrapper.trigger("mouseleave");
    expect(animation.active?.value).toBe(false);
  });

  it("ignores hover without hoverMotion", async () => {
    const wrapper = mount(GameCover, {
      props: { rom: null, title: "Hollow Knight" },
    });
    await nextTick();

    await wrapper.trigger("mouseenter");
    expect(animation.active?.value).toBe(false);
  });

  it("stops listening once unmounted", async () => {
    const wrapper = mount(GameCover, {
      props: { rom: null, title: "Hollow Knight", hoverMotion: true },
    });
    // Listeners bind once the root element ref lands, a tick after mount.
    await nextTick();
    const root = wrapper.element;

    wrapper.unmount();
    root.dispatchEvent(new MouseEvent("mouseenter"));

    expect(animation.active?.value).toBe(false);
  });
});

describe("GameCover srcset", () => {
  const rom = romFixture({
    path_cover_small: "/res/roms/1/2/cover/small.png?ts=1",
    path_cover_large: "/res/roms/1/2/cover/big.png?ts=1",
    ss_metadata: null,
    gamelist_metadata: null,
  });

  it("offers the small cover at 1x and the large one at 2x", () => {
    const wrapper = mount(GameCover, {
      props: { rom, title: "Chrono", webp: false, responsive: true },
    });
    const img = wrapper.get("img.game-cover__img");
    expect(img.attributes("srcset")).toBe(
      "/res/roms/1/2/cover/small.png?ts=1 1x, /res/roms/1/2/cover/big.png?ts=1 2x",
    );
    expect(img.attributes("src")).toContain("big.png");
  });

  it("leaves the srcset off unless the slot opts in", () => {
    const wrapper = mount(GameCover, {
      props: { rom, title: "Chrono", webp: false },
    });
    expect(
      wrapper.get("img.game-cover__img").attributes("srcset"),
    ).toBeUndefined();
  });

  it("drops the srcset for an explicit cover override", () => {
    const wrapper = mount(GameCover, {
      props: {
        rom,
        title: "Chrono",
        coverSrc: "blob:preview",
        responsive: true,
      },
    });
    expect(
      wrapper.get("img.game-cover__img").attributes("srcset"),
    ).toBeUndefined();
  });
});
