import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Pico8 from "./Pico8.vue";

const mocks = vi.hoisted(() => ({
  getRom: vi.fn(),
  runtime: {
    frameRate: 30,
    audioSampleRate: 22050,
    samplesPerFrame: 735,
    loadCart: vi.fn(),
    advance: vi.fn(),
    render: vi.fn(),
    readAudio: vi.fn(),
    dispose: vi.fn(),
  },
}));

vi.mock("vue-i18n");
vi.mock("@/services/api/rom", () => ({ default: { getRom: mocks.getRom } }));
vi.mock("@/utils", () => ({ getDownloadPath: () => "/cart.p8.png" }));
vi.mock("@/v2/utils/pico8Runtime", () => ({
  PICO8_FRAME_RATE: 30,
  PICO8_WIDTH: 128,
  PICO8_HEIGHT: 128,
  PICO8_INPUT_BITS: {
    left: 1,
    right: 2,
    up: 4,
    down: 8,
    o: 16,
    x: 32,
    pause: 64,
  },
  createPico8Runtime: async () => mocks.runtime,
}));
vi.mock("@/v2/utils/pico8Audio", () => ({
  createPico8Audio: () => Promise.reject(new Error("no audio")),
}));
vi.mock("@/v2/composables/usePlayerHero", async () => {
  const { computed } = await import("vue");
  return {
    usePlayerHero: () => ({
      romId: 1,
      heroRom: computed(() => null),
      title: computed(() => "Celeste"),
      platformLabel: computed(() => "PICO-8"),
    }),
  };
});
vi.mock("@/v2/composables/usePlaySession", () => ({
  usePlaySession: () => ({ start: vi.fn(), flush: vi.fn() }),
}));
vi.mock("@/v2/composables/usePlayerFullscreen", async () => {
  const { ref } = await import("vue");
  return {
    usePlayerFullscreen: () => ({
      isFullscreen: ref(false),
      enter: vi.fn(),
      toggle: vi.fn(),
    }),
  };
});
vi.mock("@/v2/composables/useStageActive", () => ({
  usePlayingWhile: vi.fn(),
}));
vi.mock("@/v2/composables/useUnloadGuard", () => ({
  useUnloadGuard: vi.fn(),
}));
vi.mock("@/v2/composables/useSnackbar", () => ({
  useSnackbar: () => ({ error: vi.fn() }),
}));

const PlayerShell = {
  emits: ["play"],
  template: `<div><button class="play" @click="$emit('play')" /><slot name="stage" /></div>`,
};

describe("Pico8 frame loop", () => {
  let frames: FrameRequestCallback[] = [];
  let now = 0;

  // One animation frame, 1/30s after the last.
  function step() {
    now += 1000 / 30;
    const pending = frames;
    frames = [];
    pending.forEach((cb) => cb(now));
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
    vi.spyOn(performance, "now").mockImplementation(() => now);
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(new Uint8Array([1, 2, 3]))),
    );
    vi.spyOn(console, "warn").mockImplementation(() => undefined);
    mocks.getRom.mockResolvedValue({ data: { id: 1, name: "Celeste" } });
  });

  async function play() {
    const wrapper = mount(Pico8, {
      global: {
        stubs: { PlayerShell, RBtn: true, RSpinner: true, RSwitch: true },
      },
    });
    await flushPromises();
    await wrapper.get(".play").trigger("click");
    await flushPromises();
    return wrapper;
  }

  it("runs the cart once per animation frame until unmount", async () => {
    const wrapper = await play();

    step();
    step();
    expect(mocks.runtime.render).toHaveBeenCalledTimes(2);

    wrapper.unmount();
    step();

    expect(mocks.runtime.render).toHaveBeenCalledTimes(2);
    expect(frames).toHaveLength(0);
  });

  it("stops the loop when a frame throws", async () => {
    vi.spyOn(console, "error").mockImplementation(() => undefined);
    await play();
    mocks.runtime.advance.mockImplementationOnce(() => {
      throw new Error("bad cart");
    });

    step();
    step();
    step();

    expect(mocks.runtime.render).not.toHaveBeenCalled();
    expect(mocks.runtime.dispose).toHaveBeenCalled();
  });
});
