import { mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { nextTick, type Ref } from "vue";
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
