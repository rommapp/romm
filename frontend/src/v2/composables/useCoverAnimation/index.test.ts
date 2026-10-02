import { mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { computed, defineComponent, h, nextTick, ref } from "vue";
import { useCoverAnimation } from "./index";

function setup({ cd = true, video = false } = {}) {
  const active = ref(false);
  const img = document.createElement("img");
  const videoEl = document.createElement("video");
  const play = vi.spyOn(videoEl, "play").mockResolvedValue();
  vi.spyOn(videoEl, "pause").mockImplementation(() => undefined);
  const wrapper = mount(
    defineComponent({
      setup() {
        useCoverAnimation({
          el: ref(img),
          containerEl: ref(document.createElement("div")),
          videoEl: ref(videoEl),
          animateCD: computed(() => cd),
          animateCartridge: computed(() => false),
          videoUrl: computed(() => (video ? "/clip.mp4" : null)),
          motionEnabled: computed(() => true),
          active,
        });
        return () => h("div");
      },
    }),
  );
  return { active, img, play, wrapper };
}

describe("useCoverAnimation", () => {
  let frames: FrameRequestCallback[] = [];
  let now = 0;

  function step(count = 1) {
    for (let i = 0; i < count; i++) {
      now += 50;
      const pending = frames;
      frames = [];
      pending.forEach((cb) => cb(now));
    }
  }

  beforeEach(() => {
    frames = [];
    now = 0;
    vi.stubGlobal("requestAnimationFrame", (cb: FrameRequestCallback) => {
      frames.push(cb);
      return frames.length;
    });
    vi.stubGlobal("cancelAnimationFrame", () => {
      frames = [];
    });
  });

  it("spins a disc while hovered and coasts to a stop after", async () => {
    const { active, img } = setup();

    active.value = true;
    await nextTick();
    step(10);
    expect(img.style.transform).toMatch(/rotate\([1-9]/);

    active.value = false;
    await nextTick();
    step(40);

    expect(img.style.transform).toBe("");
    step();
    expect(frames).toHaveLength(0);
  });

  it("stops spinning on unmount", async () => {
    const { active, img, wrapper } = setup();
    active.value = true;
    await nextTick();
    step(2);

    wrapper.unmount();
    const turned = img.style.transform;
    step(2);

    expect(img.style.transform).toBe(turned);
    expect(frames).toHaveLength(0);
  });

  it("plays the hover video a beat after hover, not on a passing one", async () => {
    vi.useFakeTimers();
    const { active, play } = setup({ cd: false, video: true });

    active.value = true;
    await nextTick();
    vi.advanceTimersByTime(500);
    active.value = false;
    await nextTick();
    vi.advanceTimersByTime(1000);
    expect(play).not.toHaveBeenCalled();

    active.value = true;
    await nextTick();
    vi.advanceTimersByTime(1000);
    expect(play).toHaveBeenCalledTimes(1);
  });
});
