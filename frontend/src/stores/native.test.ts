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
// Resolves true by default: the shell taking the cancel is the ordinary case,
// and a test that wants a refusal says so.
const cancelNative = vi.fn(async (_romId: number): Promise<boolean> => true);
const unsubscribe = vi.fn();
// The shell's own launch-state stream, so a test can play back what it would
// send. Captured on install rather than passed in, exactly as the bridge does.
let emit: ((state: LaunchState) => void) | null = null;

// The bridge calls are stubbed; nativeErrorMessage is kept real, since what
// the store reports out of a rejection is exactly what it is for.
vi.mock("@/services/native", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/services/native")>()),
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
// A gallery card's rom carries no file entries, so the store fetches them.
const getRom = vi.fn(async (_args: { romId: number }) => ({
  data: { files: [{ full_path: "psx/disc.chd", file_size_bytes: 700 }] },
}));
vi.mock("@/services/api/rom", () => ({ default: { getRom } }));
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
  // Keyed off the rom handed in, so a test can tell whether the store used the
  // rom it was given or the one it fetched file entries for.
  getSoleRomFile: (rom: { files?: unknown[] }) =>
    (rom.files ?? []).length > 0 ? soleFile.value : null,
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
    // As a single-rom endpoint answers. A gallery card passes `files: []`.
    files: [{ full_path: "snes/game.sfc", file_size_bytes: 4194304 }],
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
  cancelNative.mockResolvedValue(true);
  getRom.mockClear();
  getRom.mockResolvedValue({
    data: { files: [{ full_path: "psx/disc.chd", file_size_bytes: 700 }] },
  });
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

  // /api/roms omits file entries unless asked, so a rom straight off a gallery
  // card cannot say what the download endpoint will serve it as.
  it("fetches the file entries a gallery card's rom does not carry", async () => {
    const store = useNativeStore();

    await store.launch(makeRom({ files: [] }));

    expect(getRom).toHaveBeenCalledWith({ romId: 1 });
    // The fetched entries are what passthrough is then built from.
    expect(launchNative.mock.calls[0]?.[0].serverPath).toBe("snes/game.sfc");
  });

  it("asks for nothing when the rom already carries its files", async () => {
    const store = useNativeStore();

    await store.launch(makeRom());

    expect(getRom).not.toHaveBeenCalled();
    expect(launchNative.mock.calls[0]?.[0].serverPath).toBe("snes/game.sfc");
  });

  // Nothing about reading the files may fail a launch: the shell can still
  // download what the endpoint serves, it just cannot play it in place.
  it("launches anyway when the files cannot be read", async () => {
    getRom.mockRejectedValue(new Error("offline"));
    const store = useNativeStore();

    expect(await store.launch(makeRom({ files: [] }))).toBeNull();
    expect(launchNative).toHaveBeenCalledTimes(1);
    expect(launchNative.mock.calls[0]?.[0].serverPath).toBeUndefined();
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

  it("reads the message off a LaunchFailure, which is not an Error", async () => {
    // A shell carrying romm-desktop#11 rejects with a plain object, because the
    // context bridge drops an Error's own properties. String() on it yields
    // "[object Object]", which is what the user would have been shown.
    launchNative.mockRejectedValue({
      name: "LaunchError",
      code: "already-running",
      message: "Chrono Trigger is already running.",
    });
    const store = useNativeStore();

    expect(await store.launch(makeRom())).toBe(
      "Chrono Trigger is already running.",
    );
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

  // The mark goes on only once the shell has taken the cancel, so a failure
  // that arrives while the request is in flight is still the user's to see.
  it("reports a failure that lands while a cancel is in flight", async () => {
    const store = useNativeStore();
    store.install();
    // A no-op default rather than null: assigned inside the executor, which
    // control-flow analysis cannot see, so a nullable here narrows to never.
    let accept: (taken: boolean) => void = () => {};
    cancelNative.mockImplementation(
      () =>
        new Promise<boolean>((resolve) => {
          accept = resolve;
        }),
    );

    const pending = store.cancel(1);
    emit?.({
      romId: 1,
      status: "failed",
      error: { code: "emulator-not-found", message: "No PCSX2 here." },
    });
    // Nothing has suppressed it: this failure is not the cancel's.
    expect(store.consumeCancelled(1)).toBe(false);
    accept(false);
    expect(await pending).toBe(false);
  });

  it("leaves the launch alone when the shell refuses the cancel", async () => {
    // A refused cancel changes nothing: claiming otherwise would clear a launch
    // that is still coming, and the mark would swallow its real failure.
    const store = useNativeStore();
    store.install();
    emit?.({ romId: 1, status: "downloading", progress: 0.5 });
    cancelNative.mockResolvedValueOnce(false);

    expect(await store.cancel(1)).toBe(false);
    expect(store.launchStateFor(1)?.status).toBe("downloading");
    // And the failure that follows is reported, not eaten as the cancel.
    emit?.({
      romId: 1,
      status: "failed",
      error: { code: "download-failed", message: "Connection lost." },
    });
    expect(store.consumeCancelled(1)).toBe(false);
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
