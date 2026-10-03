import { flushPromises, mount, type VueWrapper } from "@vue/test-utils";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import EasyRpg from "./EasyRpg.vue";

const mocks = vi.hoisted(() => ({
  capture: vi.fn(),
  confirm: vi.fn(),
  flushPlaySession: vi.fn(),
  getRom: vi.fn(),
  playSessionStart: vi.fn(),
  prepare: vi.fn(),
  push: vi.fn(),
  pushOnUnload: vi.fn(),
  readSaves: vi.fn(),
  routeLeaveGuard: null as ((to: { fullPath: string }) => unknown) | null,
  routerReplace: vi.fn(() => Promise.resolve()),
  seededRom: null as unknown,
  setPlaying: vi.fn(),
  setStageActive: vi.fn(),
  snackbarError: vi.fn(),
  syncArgs: [] as unknown[],
  writeSaves: vi.fn(),
}));

vi.mock("vue-i18n");

vi.mock("vue-router", () => ({
  onBeforeRouteLeave: (guard: (to: { fullPath: string }) => unknown) => {
    mocks.routeLeaveGuard = guard;
  },
  useRoute: () => ({ params: { rom: "1" } }),
  useRouter: () => ({ replace: mocks.routerReplace }),
}));

vi.mock("@/plugins/router", () => ({
  ROUTES: { ROM: "rom", PLATFORM: "platform" },
}));

vi.mock("@/services/api/rom", () => ({
  default: { getRom: mocks.getRom },
}));

vi.mock("@/stores/auth", () => ({
  default: () => ({ user: { id: 7 } }),
}));

vi.mock("@/stores/playing", () => ({
  default: () => ({
    setPlaying: mocks.setPlaying,
    setStageActive: mocks.setStageActive,
  }),
}));

vi.mock("@/stores/roms", () => ({
  default: () => ({ getDetailedRom: () => mocks.seededRom }),
}));

vi.mock("@/v2/components/shared/GameCover.vue", () => ({
  default: { template: "<div />" },
}));

vi.mock("@/v2/composables/useBackgroundArt", () => ({
  useBackgroundArt: () => vi.fn(),
}));

vi.mock("@/v2/composables/useConfirm", () => ({
  useConfirm: () => mocks.confirm,
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

vi.mock("@/v2/composables/useSnackbar", () => ({
  useSnackbar: () => ({ error: mocks.snackbarError }),
}));

vi.mock("@/v2/stores/galleryRoms", () => ({
  default: () => ({ getRomById: () => null }),
}));

vi.mock("@/v2/utils/easyRpgStorage", () => ({
  easyRpgGameName: (romId: number, userId: number) => `${romId}-${userId}`,
  readEasyRpgSaves: mocks.readSaves,
  writeEasyRpgSaves: mocks.writeSaves,
}));

// The sync and storage logic have their own suites.
vi.mock("@/v2/utils/saveSync", () => ({
  DeviceSaveSync: class {
    constructor(...args: unknown[]) {
      mocks.syncArgs = args;
    }
    capture = mocks.capture;
    prepare = mocks.prepare;
    push = mocks.push;
    pushOnUnload = mocks.pushOnUnload;
  },
}));

const rom = {
  id: 1,
  name: "Yume Nikki",
  fs_name_no_ext: "Yume Nikki",
  platform_id: 2,
  platform_slug: "rpg-maker",
  rom_user: { status: null },
};

function playerSave(slot: string, content: number) {
  return {
    slot,
    fileName: `${slot}.lsd`,
    bytes: new Uint8Array([content]),
    updatedAt: 1000,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.spyOn(console, "error").mockImplementation(() => undefined);
  mocks.routeLeaveGuard = null;
  mocks.seededRom = null;
  mocks.getRom.mockResolvedValue({ data: rom });
  mocks.readSaves.mockResolvedValue([]);
  mocks.writeSaves.mockResolvedValue(undefined);
  mocks.prepare.mockResolvedValue([]);
  mocks.capture.mockResolvedValue(undefined);
  mocks.push.mockResolvedValue(true);
  mocks.confirm.mockResolvedValue(false);
});

afterEach(() => {
  vi.useRealTimers();
});

function deferred<T>(): { promise: Promise<T>; resolve: (value: T) => void } {
  let resolve: (value: T) => void = () => undefined;
  const promise = new Promise<T>((settle) => {
    resolve = settle;
  });
  return { promise, resolve };
}

function mountView(): VueWrapper {
  return mount(EasyRpg, {
    global: {
      stubs: {
        RBtn: {
          name: "RBtn",
          props: ["to"],
          emits: ["click"],
          template: "<button @click=\"$emit('click')\"><slot /></button>",
        },
        RCard: { template: "<div><slot /></div>" },
        RSpinner: true,
        RSwitch: true,
      },
    },
  });
}

async function play(): Promise<VueWrapper> {
  const wrapper = mountView();
  await flushPromises();
  await wrapper.get(".r-v2-player__play").trigger("click");
  await flushPromises();
  return wrapper;
}

describe("EasyRpg", () => {
  it("syncs the player's saves before booting the game", async () => {
    const held = [playerSave("Save01", 1), playerSave("Save02", 2)];
    mocks.readSaves.mockResolvedValue(held);
    mocks.prepare.mockResolvedValue([
      { ...playerSave("Save01", 1) },
      { ...playerSave("Save02", 9) },
      { ...playerSave("Save03", 3) },
    ]);

    const wrapper = await play();

    expect(mocks.syncArgs).toEqual([rom, 7, "easyrpg"]);
    expect(mocks.readSaves).toHaveBeenCalledWith("1-7");
    expect(mocks.prepare).toHaveBeenCalledWith(held);
    const written = mocks.writeSaves.mock.calls[0]!;
    expect(written[0]).toBe("1-7");
    expect(written[1].map((save: { slot: string }) => save.slot)).toEqual([
      "Save02",
      "Save03",
    ]);
    expect(wrapper.get("iframe").attributes("src")).toBe(
      "/assets/easyrpg/index.html?game=1-7",
    );
    expect(mocks.playSessionStart).toHaveBeenCalledWith(rom);
    wrapper.unmount();
  });

  it("stays on the start page when the saves cannot be written", async () => {
    mocks.writeSaves.mockRejectedValue(new Error("quota"));
    mocks.prepare.mockResolvedValue([playerSave("Save01", 1)]);

    const wrapper = await play();

    expect(mocks.snackbarError).toHaveBeenCalledWith(
      "play.easyrpg-saves-load-failed",
    );
    expect(wrapper.find("iframe").exists()).toBe(false);
    expect(mocks.playSessionStart).not.toHaveBeenCalled();
    wrapper.unmount();
  });

  it("captures and pushes the latest saves before leaving", async () => {
    const wrapper = await play();
    const latest = [playerSave("Save01", 5)];
    mocks.readSaves.mockResolvedValue(latest);

    expect(mocks.routeLeaveGuard?.({ fullPath: "/rom/1" })).toBe(false);
    await flushPromises();

    expect(mocks.capture).toHaveBeenCalledWith(latest);
    expect(mocks.push).toHaveBeenCalled();
    expect(mocks.confirm).not.toHaveBeenCalled();
    expect(mocks.routerReplace).toHaveBeenCalledWith("/rom/1");
    wrapper.unmount();
  });

  it("asks before leaving when a save did not reach the server", async () => {
    mocks.push.mockResolvedValue(false);
    const wrapper = await play();

    mocks.routeLeaveGuard?.({ fullPath: "/rom/1" });
    await flushPromises();

    expect(mocks.confirm).toHaveBeenCalledWith(
      expect.objectContaining({ title: "play.quit-before-save-synced" }),
    );
    expect(mocks.routerReplace).not.toHaveBeenCalled();
    wrapper.unmount();
  });

  it("waits for the fetched rom before allowing a launch", async () => {
    mocks.seededRom = rom;
    const fetched = deferred<{ data: typeof rom }>();
    mocks.getRom.mockReturnValue(fetched.promise);
    const wrapper = mountView();
    await flushPromises();

    expect(
      wrapper.get(".r-v2-player__play").attributes("disabled"),
    ).toBeDefined();

    fetched.resolve({ data: rom });
    await flushPromises();
    expect(
      wrapper.get(".r-v2-player__play").attributes("disabled"),
    ).toBeUndefined();
    wrapper.unmount();
  });

  it("does not start a game the user left while its saves synced", async () => {
    const preparing = deferred<never[]>();
    mocks.prepare.mockReturnValue(preparing.promise);
    const wrapper = mountView();
    await flushPromises();
    await wrapper.get(".r-v2-player__play").trigger("click");

    wrapper.unmount();
    preparing.resolve([]);
    await flushPromises();

    expect(mocks.playSessionStart).not.toHaveBeenCalled();
  });

  it("pushes again on leave when a poll push was still in flight", async () => {
    vi.useFakeTimers({ toFake: ["setInterval", "clearInterval"] });
    const poll = deferred<boolean>();
    mocks.push.mockReturnValueOnce(poll.promise);
    const wrapper = await play();

    vi.advanceTimersByTime(5000);
    await flushPromises();
    mocks.routeLeaveGuard?.({ fullPath: "/rom/1" });
    poll.resolve(true);
    await flushPromises();

    expect(mocks.push).toHaveBeenCalledTimes(2);
    expect(mocks.routerReplace).toHaveBeenCalledWith("/rom/1");
    wrapper.unmount();
  });

  it("sends pending saves when the page goes away", async () => {
    const wrapper = await play();

    window.dispatchEvent(new Event("pagehide"));

    expect(mocks.pushOnUnload).toHaveBeenCalled();
    expect(mocks.flushPlaySession).toHaveBeenCalled();
    wrapper.unmount();
  });
});
