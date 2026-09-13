import { beforeEach, describe, expect, it, vi } from "vitest";
import { nextTick } from "vue";
import type { SimpleRom } from "@/stores/roms";
import type {
  NativeLaunchState,
  NativeShellBridge,
} from "@/v2/types/nativeShell";

const snackbarError = vi.fn();
const snackbarInfo = vi.fn();

// Only `useI18n` is stubbed: `@/utils` reaches the real router and locale
// bundle, which needs `createI18n` to still be the genuine export.
vi.mock("vue-i18n", async (importOriginal) => ({
  ...(await importOriginal<typeof import("vue-i18n")>()),
  useI18n: () => ({ t: (key: string) => key }),
}));
vi.mock("@/v2/composables/useSnackbar", () => ({
  useSnackbar: () => ({
    error: snackbarError,
    info: snackbarInfo,
    success: vi.fn(),
    warning: vi.fn(),
  }),
}));

function makeRom(patch: Partial<SimpleRom> = {}): SimpleRom {
  return {
    id: 42,
    platform_slug: "snes",
    fs_name: "Chrono Trigger (USA).sfc",
    fs_name_no_ext: "Chrono Trigger (USA)",
    name: "Chrono Trigger",
    has_file_on_disk: true,
    files: [],
    ...patch,
  } as SimpleRom;
}

/** A stand-in for the shell's injected bridge, with controllable answers. */
function makeBridge(overrides: Partial<NativeShellBridge> = {}) {
  const listeners: ((state: NativeLaunchState) => void)[] = [];
  const bridge: NativeShellBridge = {
    shellVersion: "0.1.0",
    os: "linux",
    launch: vi.fn(async () => ({ romId: 42, emulator: "RetroArch (snes9x)" })),
    cancel: vi.fn(async () => {}),
    getPlatformSupport: vi.fn(async () => ({
      supported: true,
      emulator: "RetroArch (snes9x)",
    })),
    onLaunchState: (listener) => {
      listeners.push(listener);
      return () => listeners.splice(listeners.indexOf(listener), 1);
    },
    openSettings: vi.fn(async () => {}),
    ...overrides,
  };
  const emit = (state: NativeLaunchState) =>
    listeners.forEach((listener) => listener(state));
  return { bridge, emit };
}

// The support cache and the launch-state map are module-level singletons, so
// each test imports the composable fresh rather than leaking answers.
async function loadFresh() {
  vi.resetModules();
  const { useNativeShell } = await import("./index");
  return useNativeShell;
}

/** Let the composable's watchEffect run and its support probe settle. */
async function settle() {
  await nextTick();
  await Promise.resolve();
  await nextTick();
}

beforeEach(() => {
  vi.clearAllMocks();
  delete window.rommNative;
});

describe("outside the desktop shell", () => {
  it("reports no shell and never offers a launch", async () => {
    const useNativeShell = await loadFresh();
    const native = useNativeShell(() => makeRom());
    await settle();

    expect(native.isNativeShell.value).toBe(false);
    expect(native.canLaunch.value).toBe(false);
  });

  it("does nothing when launch is called anyway", async () => {
    const useNativeShell = await loadFresh();
    const native = useNativeShell(() => makeRom());
    await native.launch();

    expect(snackbarInfo).not.toHaveBeenCalled();
    expect(snackbarError).not.toHaveBeenCalled();
  });
});

describe("inside the desktop shell", () => {
  it("offers a launch once the shell reports support", async () => {
    const { bridge } = makeBridge();
    window.rommNative = bridge;
    const useNativeShell = await loadFresh();
    const native = useNativeShell(() => makeRom());
    await settle();

    expect(native.isNativeShell.value).toBe(true);
    expect(native.canLaunch.value).toBe(true);
    expect(native.emulatorLabel.value).toBe("RetroArch (snes9x)");
  });

  it("passes the platform's known cores to the shell", async () => {
    const { bridge } = makeBridge();
    window.rommNative = bridge;
    const useNativeShell = await loadFresh();
    useNativeShell(() => makeRom());
    await settle();

    expect(bridge.getPlatformSupport).toHaveBeenCalledWith({
      platformSlug: "snes",
      cores: ["snes9x"],
    });
  });

  it("probes each platform once however many ROMs ask", async () => {
    const { bridge } = makeBridge();
    window.rommNative = bridge;
    const useNativeShell = await loadFresh();
    useNativeShell(() => makeRom({ id: 1 }));
    useNativeShell(() => makeRom({ id: 2 }));
    useNativeShell(() => makeRom({ id: 3 }));
    await settle();

    expect(bridge.getPlatformSupport).toHaveBeenCalledTimes(1);
  });

  it("withholds the launch for a ROM with no file on disk", async () => {
    const { bridge } = makeBridge();
    window.rommNative = bridge;
    const useNativeShell = await loadFresh();
    const native = useNativeShell(() => makeRom({ has_file_on_disk: false }));
    await settle();

    expect(native.canLaunch.value).toBe(false);
    expect(bridge.getPlatformSupport).not.toHaveBeenCalled();
  });

  it("withholds the launch when the shell reports no emulator", async () => {
    const { bridge } = makeBridge({
      getPlatformSupport: vi.fn(async () => ({
        supported: false,
        reason: "no-emulator-configured" as const,
      })),
    });
    window.rommNative = bridge;
    const useNativeShell = await loadFresh();
    const native = useNativeShell(() => makeRom());
    await settle();

    expect(native.canLaunch.value).toBe(false);
    expect(native.emulatorLabel.value).toBeNull();
  });

  it("sends the download path and cores with the launch", async () => {
    const { bridge } = makeBridge();
    window.rommNative = bridge;
    const useNativeShell = await loadFresh();
    const native = useNativeShell(() => makeRom());
    await settle();
    await native.launch();

    expect(bridge.launch).toHaveBeenCalledWith({
      romId: 42,
      downloadPath: "/api/roms/42/content/Chrono Trigger (USA).sfc",
      fileName: "Chrono Trigger (USA).sfc",
      platformSlug: "snes",
      cores: ["snes9x"],
      name: "Chrono Trigger",
    });
    expect(snackbarInfo).toHaveBeenCalledWith("play.native-launching");
  });

  it("ignores a second launch while the first is still in flight", async () => {
    const { bridge, emit } = makeBridge();
    window.rommNative = bridge;
    const useNativeShell = await loadFresh();
    const native = useNativeShell(() => makeRom());
    await settle();

    emit({ romId: 42, status: "downloading", progress: 0.1 });
    await nextTick();
    await native.launch();

    expect(bridge.launch).not.toHaveBeenCalled();
  });

  it("maps a shell error code to its own message", async () => {
    const { bridge } = makeBridge({
      launch: vi.fn(async () => {
        throw Object.assign(new Error("nope"), {
          code: "emulator-not-found",
        });
      }),
    });
    window.rommNative = bridge;
    const useNativeShell = await loadFresh();
    const native = useNativeShell(() => makeRom());
    await settle();
    await native.launch();

    expect(snackbarError).toHaveBeenCalledWith(
      "play.native-error-emulator-missing",
    );
  });

  it("falls back to a generic message for an unrecognised failure", async () => {
    const { bridge } = makeBridge({
      launch: vi.fn(async () => {
        throw new Error("something else");
      }),
    });
    window.rommNative = bridge;
    const useNativeShell = await loadFresh();
    const native = useNativeShell(() => makeRom());
    await settle();
    await native.launch();

    expect(snackbarError).toHaveBeenCalledWith("play.native-error-generic");
  });

  it("tracks launch state pushed by the shell", async () => {
    const { bridge, emit } = makeBridge();
    window.rommNative = bridge;
    const useNativeShell = await loadFresh();
    const native = useNativeShell(() => makeRom());
    await settle();

    emit({ romId: 42, status: "downloading", progress: 0.5 });
    await nextTick();
    expect(native.launchState.value?.progress).toBe(0.5);
    expect(native.isLaunching.value).toBe(true);

    emit({ romId: 42, status: "exited", exitCode: 0 });
    await nextTick();
    expect(native.isLaunching.value).toBe(false);
  });

  it("ignores launch state for a different ROM", async () => {
    const { bridge, emit } = makeBridge();
    window.rommNative = bridge;
    const useNativeShell = await loadFresh();
    const native = useNativeShell(() => makeRom({ id: 42 }));
    await settle();

    emit({ romId: 99, status: "running" });
    await nextTick();
    expect(native.launchState.value).toBeNull();
  });
});
