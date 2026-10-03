import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Pico8 from "./Pico8.vue";

const mocks = vi.hoisted(() => ({
  getRom: vi.fn(),
  confirm: vi.fn(),
  exitLeave: vi.fn(),
  routeLeaveGuard: null as ((to: { fullPath: string }) => unknown) | null,
  sync: {
    prepare: vi.fn(),
    capture: vi.fn(),
    push: vi.fn(),
    captureOnUnload: vi.fn(),
  },
  syncArgs: [] as unknown[],
  runtime: {
    frameRate: 30,
    audioSampleRate: 22050,
    samplesPerFrame: 735,
    loadCart: vi.fn(),
    writeCartData: vi.fn(),
    flushCartData: vi.fn(),
    advance: vi.fn(),
    render: vi.fn(),
    readAudio: vi.fn(),
    dispose: vi.fn(),
  },
}));

vi.mock("vue-i18n");
vi.mock("vue-router", () => ({
  onBeforeRouteLeave: (guard: (to: { fullPath: string }) => unknown) => {
    mocks.routeLeaveGuard = guard;
  },
  useRoute: () => ({ params: { rom: "1" } }),
  useRouter: () => ({ replace: vi.fn() }),
}));
vi.mock("@/plugins/router", () => ({
  ROUTES: { ROM: "rom", PLATFORM: "platform" },
}));
vi.mock("@/stores/auth", () => ({ default: () => ({ user: { id: 7 } }) }));
vi.mock("@/v2/composables/useConfirm", () => ({
  useConfirm: () => mocks.confirm,
}));
vi.mock("@/v2/composables/usePlayerExit", () => ({
  usePlayerExit: () => ({
    leave: mocks.exitLeave,
    guard: () => Promise.resolve(true),
  }),
}));
vi.mock("@/v2/utils/saveSync", () => ({
  DeviceSaveSync: class {
    constructor(...args: unknown[]) {
      mocks.syncArgs = args;
    }
    prepare = mocks.sync.prepare;
    capture = mocks.sync.capture;
    push = mocks.sync.push;
    captureOnUnload = mocks.sync.captureOnUnload;
  },
}));
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
  cartDataFileName: (key: string) => `${key}.p8d.txt`,
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
  let frames = new Map<number, FrameRequestCallback>();
  let nextId = 0;
  let now = 0;

  // One animation frame, 1/30s after the last.
  function step() {
    now += 1000 / 30;
    const pending = [...frames.values()];
    frames.clear();
    pending.forEach((cb) => cb(now));
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
    vi.spyOn(performance, "now").mockImplementation(() => now);
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(new Uint8Array([1, 2, 3]))),
    );
    vi.spyOn(console, "warn").mockImplementation(() => undefined);
    mocks.getRom.mockResolvedValue({ data: { id: 1, name: "Celeste" } });
    mocks.sync.prepare.mockResolvedValue([]);
    mocks.sync.capture.mockResolvedValue(undefined);
    mocks.sync.push.mockResolvedValue(true);
    mocks.runtime.flushCartData.mockReturnValue([]);
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
    expect(frames.size).toBe(0);
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

  it("runs a single loop when replayed straight after a failed frame", async () => {
    vi.spyOn(console, "error").mockImplementation(() => undefined);
    const wrapper = await play();
    mocks.runtime.advance.mockImplementationOnce(() => {
      throw new Error("bad cart");
    });
    step();

    await wrapper.get(".play").trigger("click");
    await flushPromises();

    expect(frames.size).toBe(1);
    step();
    expect(frames.size).toBe(1);
  });
});

describe("Pico8 cart data", () => {
  const PlayerShellWithQuit = {
    emits: ["play"],
    template: `<div><button class="play" @click="$emit('play')" /><slot name="stage-actions" /><slot name="stage" /></div>`,
  };
  const back = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    vi.stubGlobal("requestAnimationFrame", () => 1);
    vi.stubGlobal("cancelAnimationFrame", () => undefined);
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(new Uint8Array([1, 2, 3]))),
    );
    vi.spyOn(console, "warn").mockImplementation(() => undefined);
    vi.spyOn(window.history, "back").mockImplementation(back);
    mocks.getRom.mockResolvedValue({ data: { id: 1, name: "Celeste" } });
    mocks.sync.prepare.mockResolvedValue([
      { slot: "celeste", bytes: new Uint8Array([9]) },
    ]);
    mocks.sync.capture.mockResolvedValue(undefined);
    mocks.sync.push.mockResolvedValue(true);
    mocks.runtime.flushCartData.mockReturnValue([
      { key: "celeste", bytes: new Uint8Array([10]) },
    ]);
    mocks.confirm.mockResolvedValue(false);
  });

  async function play() {
    const wrapper = mount(Pico8, {
      global: {
        stubs: {
          PlayerShell: PlayerShellWithQuit,
          RBtn: {
            props: { ariaLabel: { type: String, default: "" } },
            emits: ["click"],
            template: `<button :data-label="ariaLabel" @click="$emit('click')" />`,
          },
          RSpinner: true,
          RSwitch: true,
        },
      },
    });
    await flushPromises();
    await wrapper.get(".play").trigger("click");
    await flushPromises();
    return wrapper;
  }

  async function quit(wrapper: Awaited<ReturnType<typeof play>>) {
    await wrapper.get('[data-label="play.quit"]').trigger("click");
    await flushPromises();
  }

  it("restores the saved cart data before the cart loads", async () => {
    const wrapper = await play();

    expect(mocks.syncArgs).toEqual([{ id: 1, name: "Celeste" }, 7, "pico8"]);
    expect(mocks.runtime.writeCartData).toHaveBeenCalledWith([
      { key: "celeste", bytes: new Uint8Array([9]) },
    ]);
    expect(
      mocks.runtime.writeCartData.mock.invocationCallOrder[0],
    ).toBeLessThan(mocks.runtime.loadCart.mock.invocationCallOrder[0]!);
    wrapper.unmount();
  });

  it("flushes and uploads the cart data before quitting", async () => {
    const wrapper = await play();

    await quit(wrapper);

    expect(mocks.sync.capture).toHaveBeenCalledWith([
      expect.objectContaining({
        slot: "celeste",
        fileName: "celeste.p8d.txt",
        bytes: new Uint8Array([10]),
      }),
    ]);
    expect(mocks.sync.push).toHaveBeenCalled();
    expect(mocks.confirm).not.toHaveBeenCalled();
    expect(back).toHaveBeenCalled();
    expect(mocks.runtime.dispose).toHaveBeenCalled();
    wrapper.unmount();
  });

  it("flushes and sends the cart data as the page goes away", async () => {
    const wrapper = await play();

    window.dispatchEvent(new Event("pagehide"));

    expect(mocks.runtime.flushCartData).toHaveBeenCalled();
    expect(mocks.sync.captureOnUnload).toHaveBeenCalledWith([
      expect.objectContaining({ slot: "celeste" }),
    ]);
    wrapper.unmount();
  });

  it("restarts the cart when the player stays after a failed upload", async () => {
    mocks.sync.push.mockResolvedValue(false);
    const wrapper = await play();
    mocks.runtime.loadCart.mockClear();

    await quit(wrapper);

    expect(mocks.confirm).toHaveBeenCalledWith(
      expect.objectContaining({ title: "play.quit-before-save-synced" }),
    );
    expect(back).not.toHaveBeenCalled();
    expect(mocks.runtime.loadCart).toHaveBeenCalledWith(
      new Uint8Array([1, 2, 3]),
    );
    wrapper.unmount();
  });

  it("saves before a route change and then follows it", async () => {
    const wrapper = await play();

    expect(mocks.routeLeaveGuard?.({ fullPath: "/rom/1" })).toBe(false);
    await flushPromises();

    expect(mocks.sync.push).toHaveBeenCalled();
    expect(mocks.exitLeave).toHaveBeenCalledWith("/rom/1");
    wrapper.unmount();
  });
});
