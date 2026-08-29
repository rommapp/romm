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
  locationReplace: vi.fn(),
  playSessionStart: vi.fn(),
  push: vi.fn(),
  confirm: vi.fn(),
  galleryRom: null as Record<string, unknown> | null,
  routeLeaveGuard: null as ((to: { fullPath: string }) => unknown) | null,
  setPlaying: vi.fn(),
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
  useRouter: () => ({ push: mocks.push }),
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
  default: () => ({ setPlaying: mocks.setPlaying }),
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

const rom = {
  id: 1,
  name: "Windows Game",
  fs_name_no_ext: "Windows Game",
  platform_id: 2,
  platform_slug: "win9x",
  rom_user: { status: null },
};

let originalLocation: Location;

beforeAll(() => {
  originalLocation = window.location;
  Object.defineProperty(window, "location", {
    configurable: true,
    value: { ...originalLocation, replace: mocks.locationReplace },
  });
  vi.spyOn(document.body, "appendChild").mockImplementation((node) => node);
  vi.spyOn(document.head, "appendChild").mockImplementation((node) => node);
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

function stubRuntimeProbe(contentType: string, ok = true) {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok,
      headers: { get: () => contentType },
      clone: () => ({ text: async () => "" }),
    }),
  );
}

function injectedUrls(): string[] {
  return [document.head.appendChild, document.body.appendChild].flatMap((spy) =>
    vi
      .mocked(spy)
      .mock.calls.map(
        ([node]) =>
          (node as Element).getAttribute?.("src") ??
          (node as Element).getAttribute?.("href") ??
          "",
      )
      .filter(Boolean),
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  stubRuntimeProbe("text/javascript");
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

async function mountPlayer(handle: JsDosProps): Promise<VueWrapper> {
  window.Dos = vi.fn(
    (_element: HTMLDivElement, _options: Partial<JsDosOptions>) => handle,
  );
  const wrapper = mountView();
  await flushPromises();
  await wrapper.get(".r-v2-player__play").trigger("click");
  await nextTick();
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
  const CDN = "https://cdn.jsdelivr.net/npm/js-dos@8.4.1/dist";

  it("serves the runtime from the local assets when they are present", async () => {
    mountView();
    await flushPromises();

    expect(injectedUrls()).toEqual(
      expect.arrayContaining([
        "/assets/jsdos/js-dos.css",
        "/assets/jsdos/js-dos.js",
      ]),
    );
  });

  // Slim images and the Vite dev server ship no local copy, and both answer a
  // missing asset with 200 + index.html rather than a 404.
  it("falls back to the pinned CDN when the local path serves index.html", async () => {
    stubRuntimeProbe("text/html");
    mountView();
    await flushPromises();

    expect(injectedUrls()).toEqual(
      expect.arrayContaining([`${CDN}/js-dos.css`, `${CDN}/js-dos.js`]),
    );
  });

  it("points the emulator payloads at whichever base served the runtime", async () => {
    stubRuntimeProbe("text/html");
    const wrapper = await mountPlayer(makeHandle());

    const options = vi.mocked(window.Dos!).mock.calls[0]![1];
    expect(options.pathPrefix).toBe(`${CDN}/emulators/`);
    wrapper.unmount();
  });
});

describe("JsDos player exit", () => {
  it("reports when the runtime has not loaded", async () => {
    const wrapper = mountView();
    await flushPromises();

    await wrapper.get(".r-v2-player__play").trigger("click");

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

    const buttons = wrapper.findAll("button");
    await buttons[1]!.trigger("click");
    await buttons[2]!.trigger("click");

    expect(mocks.push).toHaveBeenNthCalledWith(1, {
      name: "rom",
      params: { rom: 1 },
    });
    expect(mocks.push).toHaveBeenNthCalledWith(2, {
      name: "platform",
      params: { platform: 2 },
    });
    wrapper.unmount();
  });

  it("hard-navigates after saving without awaiting stop", async () => {
    const handle = makeHandle();
    const wrapper = await mountPlayer(handle);

    await wrapper.get(".r-v2-player__quit").trigger("click");
    await flushPromises();

    expect(handle.save).toHaveBeenCalledOnce();
    expect(handle.stop).toHaveBeenCalledOnce();
    expect(mocks.locationReplace).toHaveBeenCalledWith("/rom/1");
    expect(mocks.flushPlaySession).toHaveBeenCalledOnce();
    expect(mocks.setPlaying).toHaveBeenLastCalledWith(false);
    wrapper.unmount();
    expect(handle.stop).toHaveBeenCalledOnce();
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
    expect(mocks.locationReplace).toHaveBeenCalledWith("/rom/1");
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
    expect(mocks.locationReplace).not.toHaveBeenCalled();
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
    expect(mocks.locationReplace).toHaveBeenCalledOnce();
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
    expect(mocks.locationReplace).toHaveBeenCalledOnce();
    expect(mocks.locationReplace).toHaveBeenCalledWith("/rom/1");
    wrapper.unmount();
  });

  it("converts route departure into a saved hard navigation", async () => {
    const handle = makeHandle();
    const wrapper = await mountPlayer(handle);

    expect(mocks.routeLeaveGuard?.({ fullPath: "/platform/2" })).toBe(false);
    await flushPromises();

    expect(handle.save).toHaveBeenCalledOnce();
    expect(mocks.locationReplace).toHaveBeenCalledWith("/platform/2");
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
