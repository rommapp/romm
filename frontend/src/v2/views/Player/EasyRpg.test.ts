import { flushPromises, mount, type VueWrapper } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import EasyRpg from "./EasyRpg.vue";

const mocks = vi.hoisted(() => ({
  confirm: vi.fn(),
  flushPlaySession: vi.fn(),
  getRom: vi.fn(),
  playSessionStart: vi.fn(),
  prepare: vi.fn(),
  push: vi.fn(),
  pushOnUnload: vi.fn(),
  routeLeaveGuard: null as ((to: { fullPath: string }) => unknown) | null,
  routerReplace: vi.fn(() => Promise.resolve()),
  setPlaying: vi.fn(),
  setStageActive: vi.fn(),
  snackbarError: vi.fn(),
  syncArgs: [] as unknown[],
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
  default: () => ({ getDetailedRom: () => null }),
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

vi.mock("@/v2/composables/useConfirm", () => ({
  useConfirm: () => mocks.confirm,
}));

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

// The storage and upload logic has its own suite.
vi.mock("@/v2/utils/easyRpgSaves", () => ({
  EasyRpgSaveSync: class {
    constructor(...args: unknown[]) {
      mocks.syncArgs = args;
    }
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
  user_saves: [],
};

beforeEach(() => {
  vi.spyOn(console, "error").mockImplementation(() => undefined);
  mocks.routeLeaveGuard = null;
  mocks.getRom.mockResolvedValue({ data: rom });
  mocks.prepare.mockResolvedValue(undefined);
  mocks.push.mockResolvedValue(true);
  mocks.confirm.mockResolvedValue(false);
});

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
  it("loads the user's saves before booting the game", async () => {
    const wrapper = await play();

    expect(mocks.syncArgs).toEqual([rom, "1"]);
    expect(mocks.prepare).toHaveBeenCalledWith(7);
    expect(wrapper.get("iframe").attributes("src")).toBe(
      "/assets/easyrpg/index.html?game=1",
    );
    expect(mocks.playSessionStart).toHaveBeenCalledWith(rom);
    wrapper.unmount();
  });

  it("stays on the start page when the saves cannot be loaded", async () => {
    mocks.prepare.mockRejectedValue(new Error("offline"));
    const wrapper = await play();

    expect(mocks.snackbarError).toHaveBeenCalledWith(
      "play.easyrpg-saves-load-failed",
    );
    expect(wrapper.find("iframe").exists()).toBe(false);
    expect(mocks.playSessionStart).not.toHaveBeenCalled();
    wrapper.unmount();
  });

  it("uploads the latest saves before leaving", async () => {
    const wrapper = await play();

    expect(mocks.routeLeaveGuard?.({ fullPath: "/rom/1" })).toBe(false);
    await flushPromises();

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
      expect.objectContaining({ title: "play.easyrpg-quit-without-saving" }),
    );
    expect(mocks.routerReplace).not.toHaveBeenCalled();
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
