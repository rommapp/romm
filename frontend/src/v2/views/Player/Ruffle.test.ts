import { flushPromises, mount, type VueWrapper } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { nextTick } from "vue";
import type { RuffleSourceAPI } from "@/types/ruffle";
import { zipRuffleSaves } from "@/v2/utils/ruffleSaves";
import Ruffle from "./Ruffle.vue";

const mocks = vi.hoisted(() => ({
  confirm: vi.fn(),
  exitLeave: vi.fn(),
  routeLeaveGuard: null as ((to: { fullPath: string }) => unknown) | null,
  sync: {
    prepare: vi.fn(),
    capture: vi.fn(),
    push: vi.fn(),
    captureOnUnload: vi.fn(),
  },
  getRom: vi.fn(),
  playSessionStart: vi.fn(),
  flushPlaySession: vi.fn(),
  push: vi.fn(),
  setPlaying: vi.fn(),
  setStageActive: vi.fn(),
}));

vi.mock("vue-i18n");

vi.mock("vue-router", () => ({
  onBeforeRouteLeave: (guard: (to: { fullPath: string }) => unknown) => {
    mocks.routeLeaveGuard = guard;
  },
  useRoute: () => ({ params: { rom: "1" } }),
  useRouter: () => ({ push: mocks.push }),
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
  PLAYER_SAVE_POLL_MS: 5000,
  DeviceSaveSync: class {
    prepare = mocks.sync.prepare;
    capture = mocks.sync.capture;
    push = mocks.sync.push;
    captureOnUnload = mocks.sync.captureOnUnload;
  },
}));

vi.mock("@/plugins/router", () => ({
  ROUTES: { ROM: "rom", PLATFORM: "platform" },
}));

vi.mock("@/services/api/rom", () => ({
  default: { getRom: mocks.getRom },
}));

vi.mock("@/stores/playing", () => ({
  default: () => ({
    setPlaying: mocks.setPlaying,
    setStageActive: mocks.setStageActive,
  }),
}));

vi.mock("@/stores/roms", () => ({
  default: () => ({ getDetailedRom: () => null }),
}));

vi.mock("@/utils", () => ({
  getDownloadPath: () => "/api/roms/1/content/game.swf",
}));

vi.mock("@/v2/components/shared/GameCover.vue", () => ({
  default: { template: "<div />" },
}));

vi.mock("@/v2/composables/useBackgroundArt", () => ({
  useBackgroundArt: () => vi.fn(),
}));

vi.mock("@/v2/composables/useFullscreenPref", async () => {
  const { ref } = await import("vue");
  return { useFullscreenPref: () => ({ fullscreenOnPlay: ref(false) }) };
});

vi.mock("@/v2/composables/usePageTitle", () => ({
  usePageTitle: vi.fn(),
}));

vi.mock("@/v2/composables/usePlaySession", () => ({
  usePlaySession: () => ({
    start: mocks.playSessionStart,
    flush: mocks.flushPlaySession,
  }),
}));

vi.mock("@/v2/stores/galleryRoms", () => ({
  default: () => ({ getRomById: () => null }),
}));

const rom = {
  id: 1,
  name: "Flash Game",
  fs_name_no_ext: "Flash Game",
  platform_id: 2,
  platform_slug: "flash",
  rom_user: { status: null },
};

// Swallow the Ruffle runtime <script> injections; the test drives
// window.RufflePlayer directly.
beforeEach(() => {
  const appendChild = document.body.appendChild.bind(document.body);
  vi.spyOn(document.body, "appendChild").mockImplementation((node) =>
    (node as Element).tagName === "SCRIPT" ? node : appendChild(node),
  );
});

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  mocks.sync.prepare.mockResolvedValue([]);
  mocks.sync.capture.mockResolvedValue(undefined);
  mocks.sync.push.mockResolvedValue(true);
  mocks.confirm.mockResolvedValue(false);
  mocks.getRom.mockResolvedValue({ data: rom });
  window.RufflePlayer = {
    newest: () => null,
  } as unknown as typeof window.RufflePlayer;
});

function makeRuffleSource(): RuffleSourceAPI {
  const player = Object.assign(document.createElement("div"), {
    load: vi.fn(),
    fullscreenEnabled: false,
    enterFullscreen: vi.fn(),
  });
  return {
    createPlayer: () => player,
  } as unknown as RuffleSourceAPI;
}

async function mountAndPlay(): Promise<VueWrapper> {
  const wrapper = mount(Ruffle, {
    attachTo: document.body,
    global: {
      stubs: {
        RBtn: {
          emits: ["click"],
          template: "<button @click=\"$emit('click')\"><slot /></button>",
        },
        RCard: { template: "<div><slot /></div>" },
        RIcon: true,
        RSpinner: true,
        RSwitch: true,
      },
    },
  });
  await flushPromises();
  await wrapper.get(".r-v2-player__play").trigger("click");
  await flushPromises();
  await nextTick();
  return wrapper;
}

function dispatchUnload(): Event {
  const event = new Event("beforeunload", { cancelable: true });
  window.dispatchEvent(event);
  return event;
}

describe("Ruffle launch", () => {
  it("guards the unload once a player is running", async () => {
    window.RufflePlayer = {
      newest: () => makeRuffleSource(),
    } as unknown as typeof window.RufflePlayer;

    const wrapper = await mountAndPlay();

    expect(mocks.playSessionStart).toHaveBeenCalledOnce();
    expect(dispatchUnload().defaultPrevented).toBe(true);
    wrapper.unmount();
  });

  // A failed launch used to leave the running state set, so the browser asked
  // for a leave confirmation with no game behind it.
  it("clears the running state when no Ruffle source is available", async () => {
    const wrapper = await mountAndPlay();

    expect(mocks.playSessionStart).not.toHaveBeenCalled();
    expect(mocks.setPlaying).toHaveBeenLastCalledWith(false);
    expect(dispatchUnload().defaultPrevented).toBe(false);
    wrapper.unmount();
  });
});

const HOST = window.location.hostname;
const SWF_KEY = "api/roms/1/content/game.swf/progress";

function sol(marker: number): Uint8Array {
  return new Uint8Array([
    0x00,
    0xbf,
    0,
    0,
    0,
    9,
    0x54,
    0x43,
    0x53,
    0x4f,
    marker,
  ]);
}

function stored(bytes: Uint8Array): string {
  return btoa(String.fromCharCode(...bytes));
}

describe("Ruffle saves", () => {
  beforeEach(() => {
    window.RufflePlayer = {
      newest: () => makeRuffleSource(),
    } as unknown as typeof window.RufflePlayer;
  });

  it("syncs saves left in storage and restores the synced copy", async () => {
    localStorage.setItem(`${HOST}/${SWF_KEY}`, stored(sol(1)));
    mocks.sync.prepare.mockResolvedValue([
      { slot: "autosave", bytes: zipRuffleSaves({ [SWF_KEY]: sol(2) }) },
    ]);

    const wrapper = await mountAndPlay();

    const [leftover] = mocks.sync.prepare.mock.calls[0]![0];
    expect(leftover).toMatchObject({
      slot: "autosave",
      fileName: "Flash Game.sol.zip",
    });
    expect(localStorage.getItem(`${HOST}/${SWF_KEY}`)).toBe(stored(sol(2)));
    wrapper.unmount();
  });

  it("uploads the saves and clears them from storage on quit", async () => {
    const wrapper = await mountAndPlay();
    localStorage.setItem(`${HOST}/${SWF_KEY}`, stored(sol(3)));

    expect(mocks.routeLeaveGuard?.({ fullPath: "/rom/1" })).toBe(false);
    await flushPromises();

    expect(mocks.sync.capture).toHaveBeenCalledWith([
      expect.objectContaining({ slot: "autosave" }),
    ]);
    expect(mocks.sync.push).toHaveBeenCalled();
    expect(localStorage.getItem(`${HOST}/${SWF_KEY}`)).toBeNull();
    expect(mocks.exitLeave).toHaveBeenCalledWith("/rom/1");
    expect(document.querySelector("#r-v2-ruffle-stage > *")).toBeNull();
    wrapper.unmount();
  });

  it("sends the saves and keeps them in storage as the page goes away", async () => {
    const wrapper = await mountAndPlay();
    localStorage.setItem(`${HOST}/${SWF_KEY}`, stored(sol(4)));

    window.dispatchEvent(new Event("pagehide"));

    expect(mocks.sync.captureOnUnload).toHaveBeenCalledWith([
      expect.objectContaining({ slot: "autosave" }),
    ]);
    expect(localStorage.getItem(`${HOST}/${SWF_KEY}`)).toBe(stored(sol(4)));
    wrapper.unmount();
  });

  it("restarts the game when the player stays after a failed upload", async () => {
    mocks.sync.push.mockResolvedValue(false);
    const wrapper = await mountAndPlay();
    localStorage.setItem(`${HOST}/${SWF_KEY}`, stored(sol(3)));

    mocks.routeLeaveGuard?.({ fullPath: "/rom/1" });
    await flushPromises();

    expect(mocks.confirm).toHaveBeenCalledWith(
      expect.objectContaining({ title: "play.quit-before-save-synced" }),
    );
    expect(mocks.exitLeave).not.toHaveBeenCalled();
    expect(localStorage.getItem(`${HOST}/${SWF_KEY}`)).toBe(stored(sol(3)));
    expect(document.getElementById("r-v2-ruffle-stage")?.children).toHaveLength(
      1,
    );
    wrapper.unmount();
  });
});
