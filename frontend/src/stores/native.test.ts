import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { SimpleRom } from "@/stores/roms";
import type {
  LaunchRequest,
  LaunchResult,
  LaunchState,
  PlatformSupport,
  PlatformSupportQuery,
} from "@/types/rommNative";

const shellPresent = { value: true };
const fetchPlatformSupport = vi.fn(
  async (
    _queries: PlatformSupportQuery[],
  ): Promise<Record<string, PlatformSupport>> => ({}),
);
const launchNative = vi.fn(
  async (_request: LaunchRequest): Promise<LaunchResult> => ({
    romId: 1,
    emulator: "RetroArch",
  }),
);
const cancelNative = vi.fn(async (_romId: number): Promise<void> => {});
const unsubscribe = vi.fn();
// The shell's own launch-state stream, so a test can play back what it would
// send. Captured on install rather than passed in, exactly as the bridge does.
let emit: ((state: LaunchState) => void) | null = null;

vi.mock("@/services/native", () => ({
  isNativeShell: () => shellPresent.value,
  nativeShellVersion: () => "1.2.3",
  fetchPlatformSupport,
  launchNative,
  cancelNative,
  onNativeLaunchState: (listener: (state: LaunchState) => void) => {
    emit = listener;
    return unsubscribe;
  },
}));
vi.mock("@/stores/config", () => ({ default: () => ({ config: {} }) }));
// The two rom-shape helpers are stubbed rather than reimplemented: what they
// answer is `utils`' own test, and what the store does with the answer is this
// one's. `soleFile` is the knob for "one file on disk" versus "an archive the
// endpoint builds".
const soleFile = {
  value: null as { full_path: string; file_size_bytes: number } | null,
};

vi.mock("@/utils", () => ({
  getDownloadPath: () => "/api/roms/1/content/game.sfc",
  getDownloadFileName: () => "served-name.sfc",
  getSoleRomFile: () => soleFile.value,
  getSupportedEJSCores: () => ["snes9x"],
  resolvePlatformSlug: (slug: string) => slug,
}));

const { useNativeStore } = await import("@/stores/native");

function makeRom(overrides: Partial<SimpleRom> = {}): SimpleRom {
  return {
    id: 1,
    name: "Chrono Trigger",
    fs_name: "Chrono Trigger.sfc",
    fs_name_no_ext: "Chrono Trigger",
    fs_size_bytes: 4194304,
    full_path: "snes/Chrono Trigger.sfc",
    platform_slug: "snes",
    has_file_on_disk: true,
    ...overrides,
  } as unknown as SimpleRom;
}

beforeEach(() => {
  setActivePinia(createPinia());
  shellPresent.value = true;
  emit = null;
  fetchPlatformSupport.mockClear();
  fetchPlatformSupport.mockResolvedValue({});
  launchNative.mockClear();
  launchNative.mockResolvedValue({ romId: 1, emulator: "RetroArch" });
  cancelNative.mockClear();
  unsubscribe.mockClear();
  soleFile.value = { full_path: "snes/game.sfc", file_size_bytes: 4194304 };
});

describe("useNativeStore.probe", () => {
  it("caches the shell's answer behind the per-platform getters", async () => {
    fetchPlatformSupport.mockResolvedValue({
      snes: { supported: true, emulator: "RetroArch" },
      ps3: { supported: false, reason: "unsupported-platform" },
    });
    const store = useNativeStore();

    await store.probe(["snes", "ps3"]);

    expect(store.isSupportedPlatform("snes")).toBe(true);
    expect(store.labelForPlatform("snes")).toBe("RetroArch");
    expect(store.isSupportedPlatform("ps3")).toBe(false);
  });

  it("answers for a slug asked in another case", async () => {
    fetchPlatformSupport.mockResolvedValue({
      SNES: { supported: true, emulator: "RetroArch" },
    });
    const store = useNativeStore();

    await store.probe(["snes"]);

    expect(store.isSupportedPlatform("SNES")).toBe(true);
    expect(store.isSupportedPlatform("snes")).toBe(true);
  });

  // The library grows as platforms are scanned, and re-probing what is already
  // answered would be an IPC call per boot per platform for nothing.
  it("asks only about platforms it has no answer for", async () => {
    fetchPlatformSupport.mockResolvedValue({
      snes: { supported: true, emulator: "RetroArch" },
    });
    const store = useNativeStore();
    await store.probe(["snes"]);
    fetchPlatformSupport.mockResolvedValue({
      ps2: { supported: true, emulator: "PCSX2" },
    });

    await store.probe(["snes", "ps2"]);

    expect(fetchPlatformSupport).toHaveBeenLastCalledWith([
      { platformSlug: "ps2", cores: ["snes9x"] },
    ]);
    expect(store.isSupportedPlatform("ps2")).toBe(true);
  });

  it("asks nothing at all outside the desktop shell", async () => {
    shellPresent.value = false;
    const store = useNativeStore();

    await store.probe(["snes"]);

    expect(fetchPlatformSupport).not.toHaveBeenCalled();
    expect(store.isSupportedPlatform("snes")).toBe(false);
  });

  // An unprobed platform reading as unsupported is what keeps a Play button
  // from appearing on a guess and then vanishing.
  it("treats a platform it never asked about as unsupported", async () => {
    const store = useNativeStore();

    await store.probe(["snes"]);

    expect(store.isSupportedPlatform("gba")).toBe(false);
    expect(store.supportForPlatform("gba")).toBeNull();
  });
});

describe("useNativeStore.launch", () => {
  it("names the game, its cores and where the server keeps it", async () => {
    const store = useNativeStore();

    await store.launch(makeRom());

    expect(launchNative).toHaveBeenCalledWith({
      romId: 1,
      downloadPath: "/api/roms/1/content/game.sfc",
      fileName: "served-name.sfc",
      platformSlug: "snes",
      cores: ["snes9x"],
      name: "Chrono Trigger",
      serverPath: "snes/game.sfc",
      fileSize: 4194304,
    });
  });

  // The rom's own fs_name is neither what a folder rom is served as nor what
  // it is stored as, so the request carries what the helper resolved.
  it("sends the name the endpoint will serve, not the rom's own", async () => {
    const store = useNativeStore();

    await store.launch(makeRom({ fs_name: "Art Of Fighting" }));

    expect(launchNative.mock.calls[0]?.[0].fileName).toBe("served-name.sfc");
  });

  // A rom served as an archive built per request has no single path on disk, so
  // claiming one would point the shell at a file that is not there.
  it("offers no passthrough for a rom served as a built archive", async () => {
    soleFile.value = null;
    const store = useNativeStore();

    await store.launch(makeRom());

    const request = launchNative.mock.calls[0]?.[0];
    expect(request?.serverPath).toBeUndefined();
    expect(request?.fileSize).toBeUndefined();
  });

  it("resolves with nothing to report when the shell takes the launch", async () => {
    const store = useNativeStore();

    expect(await store.launch(makeRom())).toBeNull();
  });

  // No bridge, a malformed request, or a game already running: the shell
  // rejects without ever reporting a state, so the caller has to.
  it("reports a refusal the shell never explained", async () => {
    launchNative.mockRejectedValue(new Error("Chrono Trigger is running."));
    const store = useNativeStore();

    expect(await store.launch(makeRom())).toBe("Chrono Trigger is running.");
  });

  // A failure the shell did report carries an error code this rejection
  // cannot, so it is left to the launch state to surface.
  it("stays quiet when the shell explained the failure itself", async () => {
    const store = useNativeStore();
    store.install();
    launchNative.mockImplementation(async () => {
      emit?.({
        romId: 1,
        status: "failed",
        error: { code: "emulator-not-found", message: "No RetroArch here." },
      });
      throw new Error("No RetroArch here.");
    });

    expect(await store.launch(makeRom())).toBeNull();
    expect(store.launchStateFor(1)?.error?.code).toBe("emulator-not-found");
  });
});

describe("useNativeStore launch state", () => {
  it("reads as launching until the game reaches the emulator", () => {
    const store = useNativeStore();
    store.install();

    emit?.({ romId: 1, status: "downloading", stage: "rom", progress: 0.5 });
    expect(store.isLaunching(1)).toBe(true);

    emit?.({ romId: 1, status: "running" });
    expect(store.isLaunching(1)).toBe(false);
    expect(store.launchStateFor(1)?.status).toBe("running");
  });

  it("subscribes once however often it is installed", () => {
    const store = useNativeStore();
    store.install();
    const first = emit;
    store.install();

    expect(emit).toBe(first);
  });

  // The shell has no cancelled status: it aborts the transfer, so the launch
  // fails and reports a failed download. That is the cancel, not news.
  it("owns the failure its own cancel causes, once", async () => {
    const store = useNativeStore();
    store.install();
    emit?.({ romId: 1, status: "downloading", stage: "rom" });

    await store.cancel(1);
    emit?.({
      romId: 1,
      status: "failed",
      error: { code: "download-failed", message: "Launch cancelled" },
    });

    expect(store.launchStateFor(1)).toBeNull();
    expect(store.consumeCancelled(1)).toBe(true);
    // Answered once, so a later genuine failure still reports.
    expect(store.consumeCancelled(1)).toBe(false);
  });

  it("does not swallow a failure for a launch nobody cancelled", () => {
    const store = useNativeStore();
    store.install();

    emit?.({
      romId: 1,
      status: "failed",
      error: { code: "emulator-not-found", message: "gone" },
    });

    expect(store.consumeCancelled(1)).toBe(false);
    expect(store.launchStateFor(1)?.error?.code).toBe("emulator-not-found");
  });

  it("drops the record on a cancel, which the shell never reports", async () => {
    const store = useNativeStore();
    store.install();
    emit?.({ romId: 1, status: "downloading", stage: "rom" });

    await store.cancel(1);

    expect(cancelNative).toHaveBeenCalledWith(1);
    expect(store.launchStateFor(1)).toBeNull();
    expect(store.isLaunching(1)).toBe(false);
  });
});
