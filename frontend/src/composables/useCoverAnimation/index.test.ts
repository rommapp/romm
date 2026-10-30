import { mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { computed, defineComponent, h, nextTick, ref } from "vue";
import { type UseCoverAnimation, useCoverAnimation } from "./index";

function setup({ cd = true, video = false } = {}) {
  const active = ref(false);
  const img = document.createElement("img");
  const videoEl = document.createElement("video");
  const play = vi.spyOn(videoEl, "play").mockResolvedValue();
  vi.spyOn(videoEl, "pause").mockImplementation(() => undefined);
  const load = vi.spyOn(videoEl, "load").mockImplementation(() => undefined);
  if (video) videoEl.setAttribute("src", "/clip.mp4");
  let animation!: UseCoverAnimation;
  const wrapper = mount(
    defineComponent({
      setup() {
        animation = useCoverAnimation({
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
  return { active, animation, img, load, play, videoEl, wrapper };
}

describe("useCoverAnimation", () => {
  let frames = new Map<number, FrameRequestCallback>();
  let nextId = 0;
  let now = 0;

  function step(count = 1) {
    for (let i = 0; i < count; i++) {
      now += 50;
      const pending = [...frames.values()];
      frames.clear();
      pending.forEach((cb) => cb(now));
    }
  }

  beforeEach(() => {
    frames = new Map();
    nextId = 0;
    now = 0;
    vi.stubGlobal("requestAnimationFrame", (cb: FrameRequestCallback) => {
      frames.set(++nextId, cb);
      return nextId;
    });
    vi.stubGlobal("cancelAnimationFrame", (id: number) => {
      frames.delete(id);
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
    await nextTick();
    expect(frames.size).toBe(0);
  });

  it("spins a single loop when re-hovered straight after coming to rest", async () => {
    const { active, img } = setup();
    active.value = true;
    await nextTick();
    step(10);
    active.value = false;
    await nextTick();
    for (let i = 0; i < 40 && img.style.transform !== ""; i++) step();

    active.value = true;
    await nextTick();

    expect(frames.size).toBe(1);
    step();
    expect(frames.size).toBe(1);
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
    expect(frames.size).toBe(0);
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

  it("leaves a clip alone when the hover ends before it plays", async () => {
    vi.useFakeTimers();
    const { active, load, videoEl } = setup({ cd: false, video: true });
    const pause = vi.mocked(videoEl.pause);

    active.value = true;
    await nextTick();
    vi.advanceTimersByTime(500);
    active.value = false;
    await nextTick();
    vi.advanceTimersByTime(10000);

    expect(pause).not.toHaveBeenCalled();
    expect(load).not.toHaveBeenCalled();
  });

  it("keeps a left hover clip's download for a few seconds, then drops it", async () => {
    vi.useFakeTimers();
    const { active, load, videoEl } = setup({ cd: false, video: true });

    active.value = true;
    await nextTick();
    vi.advanceTimersByTime(1000);
    active.value = false;
    await nextTick();
    vi.advanceTimersByTime(4999);
    expect(videoEl.getAttribute("src")).toBe("/clip.mp4");
    expect(load).not.toHaveBeenCalled();

    vi.advanceTimersByTime(1);
    expect(videoEl.hasAttribute("src")).toBe(false);
    expect(load).toHaveBeenCalledTimes(1);
  });

  it("replays a clip hovered again before its download is dropped", async () => {
    vi.useFakeTimers();
    const { active, load, play, videoEl } = setup({ cd: false, video: true });

    active.value = true;
    await nextTick();
    vi.advanceTimersByTime(1000);
    active.value = false;
    await nextTick();
    vi.advanceTimersByTime(3000);
    active.value = true;
    await nextTick();
    vi.advanceTimersByTime(5000);

    expect(play).toHaveBeenCalledTimes(2);
    expect(load).not.toHaveBeenCalled();
    expect(videoEl.getAttribute("src")).toBe("/clip.mp4");
  });

  it("restores a dropped hover clip source on the next hover", async () => {
    vi.useFakeTimers();
    const { active, play, videoEl } = setup({ cd: false, video: true });

    active.value = true;
    await nextTick();
    vi.advanceTimersByTime(1000);
    active.value = false;
    await nextTick();
    vi.advanceTimersByTime(5000);
    expect(videoEl.hasAttribute("src")).toBe(false);

    active.value = true;
    await nextTick();
    vi.advanceTimersByTime(1000);
    expect(videoEl.getAttribute("src")).toBe("/clip.mp4");
    expect(play).toHaveBeenCalledTimes(2);
  });

  it("drops a left clip's download at once when another clip plays", async () => {
    vi.useFakeTimers();
    const first = setup({ cd: false, video: true });
    const second = setup({ cd: false, video: true });

    first.active.value = true;
    await nextTick();
    vi.advanceTimersByTime(1000);
    first.active.value = false;
    await nextTick();
    second.active.value = true;
    await nextTick();
    vi.advanceTimersByTime(1000);

    expect(second.play).toHaveBeenCalledTimes(1);
    expect(first.load).toHaveBeenCalledTimes(1);
    expect(first.videoEl.hasAttribute("src")).toBe(false);
  });

  it("shows the still again when another clip takes over playback", async () => {
    vi.useFakeTimers();
    const first = setup({ cd: false, video: true });
    const second = setup({ cd: false, video: true });

    first.active.value = true;
    await nextTick();
    await vi.advanceTimersByTimeAsync(1000);
    expect(first.animation.isVideoPlaying.value).toBe(true);

    // The first cover stays active (keyboard focus) while the second is hovered.
    second.active.value = true;
    await nextTick();
    await vi.advanceTimersByTimeAsync(1000);

    expect(first.animation.isVideoPlaying.value).toBe(false);
    expect(second.animation.isVideoPlaying.value).toBe(true);
  });

  it("keeps the still when play settles after the cover was left", async () => {
    vi.useFakeTimers();
    const { active, animation, play } = setup({ cd: false, video: true });
    let settle!: () => void;
    play.mockImplementation(
      () => new Promise<void>((resolve) => (settle = resolve)),
    );

    active.value = true;
    await nextTick();
    vi.advanceTimersByTime(1000);
    active.value = false;
    await nextTick();
    settle();
    await vi.advanceTimersByTimeAsync(0);

    expect(animation.isVideoPlaying.value).toBe(false);
  });

  it("drops the hover clip source on unmount", () => {
    const { load, videoEl, wrapper } = setup({ cd: false, video: true });

    wrapper.unmount();

    expect(videoEl.hasAttribute("src")).toBe(false);
    expect(load).toHaveBeenCalledTimes(1);
  });
});
