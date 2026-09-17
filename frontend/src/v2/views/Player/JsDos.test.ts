import { flushPromises, mount, type VueWrapper } from "@vue/test-utils";
import {
  afterAll,
  beforeAll,
  beforeEach,
  describe,
  expect,
  it,
  vi,
} from "vitest";
import { nextTick } from "vue";
import type { JsDosOptions, JsDosProps } from "@/types/js-dos";
import JsDos from "./JsDos.vue";

const mocks = vi.hoisted(() => ({
  flushPlaySession: vi.fn(),
  getRom: vi.fn(),
  loadRuntime: vi.fn(),
  locationReplace: vi.fn(),
  playSessionStart: vi.fn(),
  routerReplace: vi.fn(() => Promise.resolve()),
  confirm: vi.fn(),
  galleryRom: null as Record<string, unknown> | null,
  routeLeaveGuard: null as ((to: { fullPath: string }) => unknown) | null,
  setPlaying: vi.fn(),
  setStageActive: vi.fn(),
  snackbarError: vi.fn(),
  userId: 7,
}));

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

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
  default: () => ({ user: { id: mocks.userId } }),
}));

vi.mock("@/stores/playing", () => ({
  default: () => ({
    setPlaying: mocks.setPlaying,
    setStageActive: mocks.setStageActive,
  }),
}));

vi.mock("@/stores/roms", () => ({
  default: () => ({ currentRom: null }),
}));

vi.mock("@/utils", () => ({
  getDownloadPath: () => "/api/roms/1/content/game.jsdos",
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
  default: () => ({ getRomById: () => mocks.galleryRom }),
}));

// The runtime is a document-level singleton with its own suite; here it only
// has to say which base the emulator payloads follow.
vi.mock("./jsDosRuntime", () => ({
  loadJsDosRuntime: mocks.loadRuntime,
}));

const rom = {
  id: 1,
  name: "Windows Game",
  fs_name_no_ext: "Windows Game",
  platform_id: 2,
  platform_slug: "win9x",
  rom_user: { status: null },
};

const LOCAL_BASE = "/assets/jsdos";
const CDN_BASE = "https://cdn.jsdelivr.net/npm/js-dos@8.4.1/dist";

let originalLocation: Location;

function setIsolated(isolated: boolean) {
  Object.defineProperty(window, "crossOriginIsolated", {
    configurable: true,
    value: isolated,
  });
}

beforeAll(() => {
  originalLocation = window.location;
  Object.defineProperty(window, "location", {
    configurable: true,
    value: { ...originalLocation, replace: mocks.locationReplace },
  });
  vi.spyOn(console, "error").mockImplementation(() => undefined);
});

afterAll(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  Object.defineProperty(window, "location", {
    configurable: true,
    value: originalLocation,
  });
});

beforeEach(() => {
  vi.clearAllMocks();
  setIsolated(false);
  mocks.loadRuntime.mockResolvedValue(LOCAL_BASE);
  mocks.galleryRom = null;
  mocks.routeLeaveGuard = null;
  mocks.userId = 7;
  mocks.confirm.mockResolvedValue(false);
  mocks.getRom.mockResolvedValue({ data: rom });
  window.Dos = undefined;
});

function mountView(): VueWrapper {
  return mount(JsDos, {
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

// The runtime script defines `Dos` once it has loaded, so the stub lands
// after the mount has injected it.
async function mountPlayer(handle: JsDosProps): Promise<VueWrapper> {
  const wrapper = mountView();
  await flushPromises();
  window.Dos = vi.fn(
    (_element: HTMLDivElement, _options: Partial<JsDosOptions>) => handle,
  );
  await wrapper.get(".r-v2-player__play").trigger("click");
  await flushPromises();
  return wrapper;
}

function makeHandle(saveResult = true) {
  return {
    save: vi.fn().mockResolvedValue(saveResult),
    setNoCloud: vi.fn(),
    stop: vi.fn(() => new Promise<void>(() => undefined)),
  };
}

describe("JsDos runtime loading", () => {
  it("starts loading the runtime alongside the ROM payload", async () => {
    mountView();
    await flushPromises();

    expect(mocks.loadRuntime).toHaveBeenCalled();
  });

  it("points the emulator payloads at whichever base served the runtime", async () => {
    mocks.loadRuntime.mockResolvedValue(CDN_BASE);
    const wrapper = await mountPlayer(makeHandle());

    const options = vi.mocked(window.Dos!).mock.calls[0]![1];
    expect(options.pathPrefix).toBe(`${CDN_BASE}/emulators/`);
    wrapper.unmount();
  });

  it("reports a runtime that never arrived", async () => {
    mocks.loadRuntime.mockRejectedValue(new Error("network"));
    const wrapper = mountView();
    await flushPromises();

    await wrapper.get(".r-v2-player__play").trigger("click");
    await flushPromises();

    expect(mocks.snackbarError).toHaveBeenCalledWith(
      "play.stream-error-generic",
    );
    expect(mocks.setPlaying).not.toHaveBeenCalledWith(true);
    wrapper.unmount();
  });
});

describe("JsDos player exit", () => {
  it("reports when the runtime defined no factory", async () => {
    const wrapper = mountView();
    await flushPromises();

    await wrapper.get(".r-v2-player__play").trigger("click");
    await flushPromises();

    expect(mocks.snackbarError).toHaveBeenCalledWith(
      "play.stream-error-generic",
    );
    expect(mocks.setPlaying).not.toHaveBeenCalledWith(true);
    wrapper.unmount();
  });

  it("uses the gallery seed for back navigation while the ROM loads", async () => {
    mocks.galleryRom = rom;
    mocks.getRom.mockReturnValue(new Promise(() => undefined));
    const wrapper = mountView();
    await nextTick();

    const [, toRom, toPlatform] = wrapper.findAllComponents({ name: "RBtn" });

    expect(toRom!.props("to")).toEqual({ name: "rom", params: { rom: 1 } });
    expect(toPlatform!.props("to")).toEqual({
      name: "platform",
      params: { platform: 2 },
    });
    wrapper.unmount();
  });

  it("leaves within the app after saving without awaiting stop", async () => {
    const handle = makeHandle();
    const wrapper = await mountPlayer(handle);

    await wrapper.get(".r-v2-player__quit").trigger("click");
    await flushPromises();

    expect(handle.save).toHaveBeenCalledOnce();
    expect(handle.stop).toHaveBeenCalledOnce();
    expect(mocks.routerReplace).toHaveBeenCalledWith("/rom/1");
    expect(mocks.locationReplace).not.toHaveBeenCalled();
    expect(mocks.flushPlaySession).toHaveBeenCalledOnce();
    expect(mocks.setPlaying).toHaveBeenLastCalledWith(false);
    wrapper.unmount();
    expect(handle.stop).toHaveBeenCalledOnce();
  });

  // A player document opened directly is cross-origin isolated, and the rest
  // of the app cannot embed third-party images under that policy.
  it("replaces an isolated document after saving", async () => {
    setIsolated(true);
    const handle = makeHandle();
    const wrapper = await mountPlayer(handle);

    await wrapper.get(".r-v2-player__quit").trigger("click");
    await flushPromises();

    expect(handle.save).toHaveBeenCalledOnce();
    expect(mocks.locationReplace).toHaveBeenCalledWith("/rom/1");
    expect(mocks.routerReplace).not.toHaveBeenCalled();
    wrapper.unmount();
  });

  it("lets a departure from the launch view through", async () => {
    const wrapper = mountView();
    await flushPromises();

    expect(mocks.routeLeaveGuard?.({ fullPath: "/platform/2" })).toBe(true);
    expect(mocks.locationReplace).not.toHaveBeenCalled();
    wrapper.unmount();
  });

  it("replaces an isolated document on departure from the launch view", async () => {
    setIsolated(true);
    const wrapper = mountView();
    await flushPromises();

    expect(mocks.routeLeaveGuard?.({ fullPath: "/platform/2" })).toBe(false);
    expect(mocks.locationReplace).toHaveBeenCalledWith("/platform/2");
    wrapper.unmount();
  });

  it("keeps the player open when the final save is not confirmed", async () => {
    const handle = makeHandle(false);
    const wrapper = await mountPlayer(handle);

    await wrapper.get(".r-v2-player__quit").trigger("click");
    await flushPromises();

    expect(mocks.snackbarError).toHaveBeenCalledWith(
      "play.stream-save-unconfirmed",
    );
    expect(handle.stop).not.toHaveBeenCalled();
    expect(mocks.routerReplace).not.toHaveBeenCalled();
    expect(mocks.locationReplace).not.toHaveBeenCalled();
    expect(mocks.flushPlaySession).not.toHaveBeenCalled();
    expect(mocks.setPlaying).not.toHaveBeenCalledWith(false);
    expect(
      wrapper.get(".r-v2-player__quit").attributes("disabled"),
    ).toBeUndefined();
    wrapper.unmount();
  });

  it("can discard recent changes and exit after a failed save", async () => {
    mocks.confirm.mockResolvedValue(true);
    const handle = makeHandle(false);
    const wrapper = await mountPlayer(handle);

    await wrapper.get(".r-v2-player__quit").trigger("click");
    await flushPromises();

    expect(handle.stop).toHaveBeenCalledOnce();
    expect(mocks.flushPlaySession).toHaveBeenCalledOnce();
    expect(mocks.setPlaying).toHaveBeenLastCalledWith(false);
    expect(mocks.routerReplace).toHaveBeenCalledWith("/rom/1");
    wrapper.unmount();
  });

  it("keeps the player open when the final save fails", async () => {
    const handle = makeHandle();
    handle.save.mockRejectedValue(new Error("save failed"));
    const wrapper = await mountPlayer(handle);

    await wrapper.get(".r-v2-player__quit").trigger("click");
    await flushPromises();

    expect(mocks.snackbarError).toHaveBeenCalledWith(
      "play.stream-save-unconfirmed",
    );
    expect(handle.stop).not.toHaveBeenCalled();
    expect(mocks.routerReplace).not.toHaveBeenCalled();
    wrapper.unmount();
  });

  it("ignores a second quit while the final save is pending", async () => {
    let finishSave: ((saved: boolean) => void) | undefined;
    const handle = makeHandle();
    handle.save.mockReturnValue(
      new Promise<boolean>((resolve) => {
        finishSave = resolve;
      }),
    );
    const wrapper = await mountPlayer(handle);

    await wrapper.get(".r-v2-player__quit").trigger("click");
    await wrapper.get(".r-v2-player__quit").trigger("click");
    expect(handle.save).toHaveBeenCalledOnce();

    finishSave?.(true);
    await flushPromises();
    expect(mocks.routerReplace).toHaveBeenCalledOnce();
    wrapper.unmount();
  });

  it("ignores route departure while another final save is pending", async () => {
    let finishSave: ((saved: boolean) => void) | undefined;
    const handle = makeHandle();
    handle.save.mockReturnValue(
      new Promise<boolean>((resolve) => {
        finishSave = resolve;
      }),
    );
    const wrapper = await mountPlayer(handle);

    await wrapper.get(".r-v2-player__quit").trigger("click");
    expect(mocks.routeLeaveGuard?.({ fullPath: "/platform/2" })).toBe(false);
    expect(handle.save).toHaveBeenCalledOnce();

    finishSave?.(true);
    await flushPromises();
    expect(mocks.routerReplace).toHaveBeenCalledOnce();
    expect(mocks.routerReplace).toHaveBeenCalledWith("/rom/1");
    wrapper.unmount();
  });

  it("saves before following a route departure", async () => {
    const handle = makeHandle();
    const wrapper = await mountPlayer(handle);

    expect(mocks.routeLeaveGuard?.({ fullPath: "/platform/2" })).toBe(false);
    await flushPromises();

    expect(handle.save).toHaveBeenCalledOnce();
    expect(mocks.routerReplace).toHaveBeenCalledWith("/platform/2");
    wrapper.unmount();
  });

  it("only performs best-effort stop during unmount", async () => {
    const handle = makeHandle();
    const wrapper = await mountPlayer(handle);

    wrapper.unmount();

    expect(handle.save).not.toHaveBeenCalled();
    expect(handle.stop).toHaveBeenCalledOnce();
    expect(mocks.setPlaying).toHaveBeenLastCalledWith(false);
  });

  it("warns before reloading while the game is running", async () => {
    const handle = makeHandle();
    const wrapper = await mountPlayer(handle);
    const event = new Event("beforeunload", {
      cancelable: true,
    }) as BeforeUnloadEvent;

    window.dispatchEvent(event);

    expect(event.defaultPrevented).toBe(true);
    wrapper.unmount();
  });

  it("uses a stable browser-local save key scoped to the RomM user", async () => {
    const firstHandle = makeHandle();
    const firstWrapper = await mountPlayer(firstHandle);
    const firstOptions = vi.mocked(window.Dos!).mock.calls[0]![1];
    const firstKey = await firstOptions.fsChanges?.urlToKey?.(
      "/api/roms/1/content/renamed.jsdos",
    );
    firstWrapper.unmount();

    mocks.userId = 8;
    const secondHandle = makeHandle();
    const secondWrapper = await mountPlayer(secondHandle);
    const secondOptions = vi.mocked(window.Dos!).mock.calls[0]![1];
    const secondKey = await secondOptions.fsChanges?.urlToKey?.(
      "/api/roms/1/content/renamed-again.jsdos",
    );

    expect(firstKey).toBe("romm-user-7-rom-1.changes");
    expect(secondKey).toBe("romm-user-8-rom-1.changes");
    secondWrapper.unmount();
  });
});
