import { RBtn, RSelect } from "@v2/lib";
import { flushPromises, mount, type VueWrapper } from "@vue/test-utils";
import { readFileSync } from "node:fs";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { defineComponent } from "vue";
import type { DetailedRom } from "@/stores/roms";
import type { LaunchState, SaveSyncOutcome } from "@/types/rommNative";
import EmulatorJS from "./EmulatorJS.vue";

const mocks = vi.hoisted(() => ({
  getRom: vi.fn(),
  getFirmware: vi.fn(),
  launch: vi.fn(),
  cancel: vi.fn(),
  canPlayEJS: true,
  canPlayNative: false,
  emulator: null as string | null,
  launching: false,
  launchState: null as LaunchState | null,
  /** What the platform's core map offers, which is what the setup panel lists
   *  and what the first core resolves from. */
  cores: [] as string[],
  /** Whether the shell takes the page's full-screen answer with it. */
  honoursFullscreen: false,
  // A box, like syncOutcome: the preference is a ref the view keeps, so a test
  // that flips it has to write through the same object.
  fullscreen: { value: false },
  // A box rather than the value: the store's getter has to read something the
  // watcher can track, so the mock swaps this for a reactive object.
  syncOutcome: { value: null as SaveSyncOutcome | null },
}));

vi.mock("vue-i18n", () => ({
  useI18n: () => ({
    // Rendered params matter to the progress readout, so they are kept.
    t: (key: string, params?: Record<string, unknown>) =>
      params ? `${key}:${Object.values(params).join(",")}` : key,
  }),
}));

vi.mock("@/services/api/rom", () => ({ default: { getRom: mocks.getRom } }));

vi.mock("@/services/api/firmware", () => ({
  default: { getFirmware: mocks.getFirmware },
}));

vi.mock("@/services/api/save", () => ({
  AUTOSAVE_SLOT: "autosave",
  SAVE_SLOT_MAX_LENGTH: 32,
}));

vi.mock("@/stores/config", () => ({
  default: () => ({
    config: { EJS_NETPLAY_ENABLED: false },
    getEJSDefaultCore: () => null,
    getEJSCoreOptions: () => ({}),
  }),
}));

vi.mock("@/stores/playing", async () => {
  const { ref } = await import("vue");
  return { default: () => ({ playing: ref(false) }) };
});

vi.mock("@/stores/native", async () => {
  const { reactive } = await import("vue");
  Object.assign(mocks, { syncOutcome: reactive(mocks.syncOutcome) });
  return {
    useNativeStore: () => ({
      isLaunching: () => mocks.launching,
      labelForPlatform: () => mocks.emulator,
      launchStateFor: () => mocks.launchState,
      syncFor: () => mocks.syncOutcome.value,
      honoursFullscreen: mocks.honoursFullscreen,
      launch: mocks.launch,
      cancel: mocks.cancel,
    }),
  };
});

vi.mock("@/utils", () => ({
  areThreadsRequiredForEJSCore: () => false,
  formatRelativeDate: (value: string) => value,
  getSupportedEJSCores: () => mocks.cores,
}));

vi.mock("@/v2/composables/useCanPlay", async () => {
  const { computed } = await import("vue");
  return {
    useCanPlay: () => ({
      canPlayEJS: computed(() => mocks.canPlayEJS),
      canPlayNative: computed(() => mocks.canPlayNative),
    }),
  };
});

vi.mock("@/v2/composables/useActivityPresence", () => ({
  useActivityPresence: () => ({
    start: vi.fn(),
    stopHeartbeat: vi.fn(),
    emitStop: vi.fn(),
  }),
}));

vi.mock("@/v2/composables/useCoverArt", async () => {
  const { computed } = await import("vue");
  return {
    useCoverArt: () => ({
      style: computed(() => "cover_path"),
      coverUrl: computed(() => null),
      fallbackUrl: computed(() => null),
    }),
  };
});

vi.mock("@/v2/composables/useFullscreenFallback", () => ({
  useFullscreenFallback: vi.fn(),
}));

vi.mock("@/v2/composables/useFullscreenPref", async () => {
  const { reactive } = await import("vue");
  Object.assign(mocks, { fullscreen: reactive(mocks.fullscreen) });
  return { useFullscreenPref: () => ({ fullscreenOnPlay: mocks.fullscreen }) };
});

vi.mock("@/v2/composables/useInputModality", async () => {
  const { ref } = await import("vue");
  return { useInputModality: () => ({ modality: ref("mouse") }) };
});

vi.mock("@/v2/composables/usePlaySession", () => ({
  usePlaySession: () => ({ start: vi.fn(), flush: vi.fn() }),
}));

vi.mock("@/v2/composables/usePlayerHero", async () => {
  const { computed, ref } = await import("vue");
  return {
    usePlayerHero: (rom: { value: DetailedRom | null }) => ({
      romId: 7,
      heroRom: ref(rom.value ?? ROM),
      title: computed(() => ROM.name),
      platformLabel: computed(() => "PlayStation 2"),
    }),
  };
});

vi.mock("@/v2/composables/usePlayerNav", () => ({
  usePlayerNav: () => ({ backToRom: vi.fn(), backToPlatform: vi.fn() }),
}));

vi.mock("@/v2/composables/useSnackbar", () => ({
  useSnackbar: () => ({
    success: vi.fn(),
    error: vi.fn(),
    info: vi.fn(),
  }),
}));

vi.mock("@/v2/composables/useStageActive", () => ({ useStageActive: vi.fn() }));

vi.mock("@/v2/composables/useUnloadGuard", () => ({ useUnloadGuard: vi.fn() }));

const ROM = {
  id: 7,
  name: "Shadow of the Colossus",
  platform_id: 4,
  platform_slug: "ps2",
  has_file_on_disk: true,
  files: [],
  user_saves: [],
  user_states: [],
  user_screenshots: [],
} as unknown as DetailedRom;

// The launch flourish reaches into the cover, so the stub has to answer.
const GameCoverStub = defineComponent({
  setup(_, { expose }) {
    expose({ playLoad: () => 0 });
    return () => null;
  },
});

async function launchScreen(): Promise<VueWrapper> {
  const wrapper = mount(EmulatorJS, {
    shallow: true,
    global: {
      renderStubDefaultSlot: true,
      stubs: { GameCover: GameCoverStub },
    },
  });
  await flushPromises();
  return wrapper;
}

function playLabels(wrapper: VueWrapper): string[] {
  return wrapper.findAll(".r-v2-ejs__play").map((btn) => btn.text());
}

function playDisabled(wrapper: VueWrapper): unknown[] {
  return wrapper
    .findAllComponents(RBtn)
    .filter((btn) => btn.classes().includes("r-v2-ejs__play"))
    .map((btn) => btn.props("disabled"));
}

function cancelBtn(wrapper: VueWrapper) {
  return wrapper
    .findAllComponents(RBtn)
    .find((btn) => btn.classes().includes("r-v2-ejs__native-cancel"));
}

function playIcons(wrapper: VueWrapper): unknown[] {
  return wrapper
    .findAllComponents(RBtn)
    .filter((btn) => btn.classes().includes("r-v2-ejs__play"))
    .map((btn) => btn.props("prependIcon"));
}

beforeEach(() => {
  mocks.getRom.mockResolvedValue({ data: ROM });
  mocks.getFirmware.mockResolvedValue({ data: [] });
  mocks.launch.mockResolvedValue(null);
  mocks.cancel.mockResolvedValue(true);
  mocks.canPlayEJS = true;
  mocks.canPlayNative = false;
  mocks.emulator = null;
  mocks.launching = false;
  mocks.launchState = null;
  mocks.syncOutcome.value = null;
  mocks.cores = [];
  mocks.honoursFullscreen = false;
  mocks.fullscreen.value = false;
});

describe("EmulatorJS launch screen — play routes", () => {
  it("offers only the in-browser route outside the desktop shell", async () => {
    expect(playLabels(await launchScreen())).toEqual(["play.play"]);
  });

  it("puts the native launch above the in-browser one, and names both", async () => {
    mocks.canPlayNative = true;
    mocks.emulator = "PCSX2";

    expect(playLabels(await launchScreen())).toEqual([
      "play.play-native-in:PCSX2",
      "play.play-in-browser",
    ]);
  });

  // The shell sends "RetroArch (snes9x)" / "PCSX2 (to install)"; the qualifier
  // does not fit beside the label and overflowed the button.
  it.each([
    ["RetroArch (snes9x)", "play.play-native-in:RetroArch"],
    ["PCSX2 (to install)", "play.play-native-in:PCSX2"],
    ["RetroArch (Flatpak)", "play.play-native-in:RetroArch"],
    ["PCSX2", "play.play-native-in:PCSX2"],
  ])("names %s on the button as %s", async (emulator, expected) => {
    mocks.canPlayNative = true;
    mocks.emulator = emulator;

    expect(playLabels(await launchScreen())[0]).toBe(expected);
  });

  it("falls back to an unnamed native label when no emulator resolves", async () => {
    mocks.canPlayNative = true;

    expect(playLabels(await launchScreen())[0]).toBe("play.play-native");
  });

  it("keeps the play glyph on the launch and marks the other for the browser", async () => {
    mocks.canPlayNative = true;

    expect(playIcons(await launchScreen())).toEqual(["mdi-play", "mdi-web"]);
  });

  it("leaves the play glyph on the lone in-browser button", async () => {
    expect(playIcons(await launchScreen())).toEqual(["mdi-play"]);
  });

  it("hands the rom to the shell when the native button is pressed", async () => {
    mocks.canPlayNative = true;
    const wrapper = await launchScreen();

    await wrapper.findAll(".r-v2-ejs__play")[0].trigger("click");

    // No core map for the platform is no core to ask for, which leaves the
    // shell to resolve one from the candidates it is given.
    expect(mocks.launch).toHaveBeenCalledWith(ROM, {
      core: undefined,
      fullscreen: false,
    });
  });

  // The setup panel sits beside both buttons, so a choice made in it that only
  // reached one of them would be a panel that lies about half the page.
  it("sends the panel's core and full-screen answers with the launch", async () => {
    mocks.canPlayNative = true;
    mocks.cores = ["mgba", "vba_next"];
    mocks.fullscreen.value = true;
    const wrapper = await launchScreen();

    await wrapper.findAll(".r-v2-ejs__play")[0].trigger("click");

    expect(mocks.launch).toHaveBeenCalledWith(ROM, {
      core: "mgba",
      fullscreen: true,
    });
  });
});

describe("EmulatorJS launch screen — what the setup panel claims", () => {
  beforeEach(() => {
    mocks.canPlayNative = true;
    mocks.cores = ["mgba", "vba_next"];
  });

  it("says the core and full-screen answers reach the shell", async () => {
    mocks.honoursFullscreen = true;

    expect((await launchScreen()).find(".r-v2-ejs__setup-note").text()).toBe(
      "play.native-applies-core-fullscreen",
    );
  });

  it("claims only the core on a shell that cannot take the rest", async () => {
    expect((await launchScreen()).find(".r-v2-ejs__setup-note").text()).toBe(
      "play.native-applies-core",
    );
  });

  it("says nothing about a route the page is not offering", async () => {
    mocks.canPlayNative = false;

    expect((await launchScreen()).find(".r-v2-ejs__setup-note").exists()).toBe(
      false,
    );
  });

  // The line would name a select that is not rendered: a platform with one core
  // is not offering a choice to carry anywhere.
  it("says nothing where there is no core to choose", async () => {
    mocks.cores = ["mgba"];
    mocks.honoursFullscreen = true;

    expect((await launchScreen()).find(".r-v2-ejs__setup-note").exists()).toBe(
      false,
    );
  });
});

describe("EmulatorJS launch screen — a platform only the shell can run", () => {
  beforeEach(() => {
    mocks.canPlayEJS = false;
    mocks.canPlayNative = true;
  });

  it("drops everything EmulatorJS owns, leaving the native launch", async () => {
    const wrapper = await launchScreen();

    expect(playLabels(wrapper)).toEqual(["play.play-native"]);
    expect(wrapper.find(".r-v2-ejs__resume").exists()).toBe(false);
    expect(wrapper.find(".r-v2-ejs__setup").exists()).toBe(false);
    expect(wrapper.find(".r-v2-ejs__brand").exists()).toBe(false);
  });
});

describe("EmulatorJS launch screen — a launch in flight", () => {
  beforeEach(() => {
    mocks.canPlayNative = true;
    mocks.launching = true;
  });

  it("reads the shell's progress off the button and offers a cancel", async () => {
    mocks.launchState = {
      romId: 7,
      status: "downloading",
      progress: 0.42,
    } as LaunchState;
    const wrapper = await launchScreen();

    expect(playLabels(wrapper)[0]).toBe("play.native-downloading:42");
    expect(wrapper.text()).toContain("play.native-cancel");
  });

  it("drops the qualifier from the emulator the shell is setting up", async () => {
    mocks.launchState = {
      romId: 7,
      status: "downloading",
      stage: "emulator",
      emulator: "RetroArch (snes9x)",
    } as LaunchState;

    expect(playLabels(await launchScreen())[0]).toBe(
      "play.native-preparing:RetroArch",
    );
  });

  it("names the stage the shell reports over the raw percentage", async () => {
    mocks.launchState = {
      romId: 7,
      status: "downloading",
      stage: "firmware",
      firmware: "scph5501.bin",
      progress: 0.1,
    } as LaunchState;

    expect(playLabels(await launchScreen())[0]).toBe(
      "play.native-fetching-firmware:scph5501.bin",
    );
  });

  // Booting a core here would run a second session for the same game while the
  // shell is still fetching it.
  it("closes the in-browser route while the shell is working", async () => {
    expect(playDisabled(await launchScreen())).toEqual([true, true]);
  });

  // The control stays on screen while the shell answers, so a second press
  // would ask twice and report twice.
  it("asks once however often the cancel is pressed", async () => {
    let release: () => void = () => {};
    mocks.cancel.mockImplementation(
      () =>
        new Promise<boolean>((resolve) => {
          release = () => resolve(true);
        }),
    );
    const wrapper = await launchScreen();
    const cancel = cancelBtn(wrapper);

    await cancel?.trigger("click");
    await cancel?.trigger("click");
    release();
    await flushPromises();

    expect(mocks.cancel).toHaveBeenCalledTimes(1);
  });

  it("asks the shell to abort when the cancel is pressed", async () => {
    const wrapper = await launchScreen();

    await cancelBtn(wrapper)?.trigger("click");

    expect(mocks.cancel).toHaveBeenCalledWith(7);
  });
});

// The shell moves saves on the server before the emulator starts and after it
// exits, so the save list this page fetched on mount is stale by the time a
// native launch is done with it.
describe("EmulatorJS launch screen — a save the shell moved", () => {
  function slotItems(wrapper: VueWrapper): unknown[] {
    const select = wrapper
      .findAllComponents(RSelect)
      .find((c) => c.props("info") === "play.slot-tooltip");
    return (select?.props("items") as unknown[]) ?? [];
  }

  // Not the call count: nothing unmounts the wrappers earlier tests mounted,
  // and their watchers are still live on the same mock store, so one outcome
  // re-reads every rom on screen. What this wrapper shows is its own business.
  it("re-reads the rom once the shell reports what happened to the save", async () => {
    const wrapper = await launchScreen();
    expect(slotItems(wrapper)).toHaveLength(2);

    mocks.getRom.mockResolvedValue({
      data: { ...ROM, user_saves: [{ slot: "slots/2" }] },
    });
    mocks.syncOutcome.value = { action: "downloaded" };
    await flushPromises();

    expect(slotItems(wrapper)).toHaveLength(3);
  });

  it("leaves the save list alone when the shell says nothing", async () => {
    const wrapper = await launchScreen();

    await flushPromises();

    expect(slotItems(wrapper)).toHaveLength(2);
  });
});

// An icon class the font does not define renders as an empty circle rather
// than failing, so the name alone is never evidence that a glyph exists.
describe("the native affordances' icons", () => {
  const MDI_CSS = readFileSync(
    "node_modules/@mdi/font/css/materialdesignicons.css",
    "utf8",
  );

  it.each([
    "mdi-play",
    "mdi-web",
    "mdi-loading",
    "mdi-spin",
    "mdi-close-circle-outline",
    "mdi-desktop-classic",
  ])("%s is a real class in the bundled font", (name) => {
    // Matched on the rule the font actually declares, not the bare name, or
    // "mdi-play" would be satisfied by "mdi-playlist-play".
    expect(MDI_CSS).toMatch(new RegExp(`\\.${name}::?before`));
  });
});
