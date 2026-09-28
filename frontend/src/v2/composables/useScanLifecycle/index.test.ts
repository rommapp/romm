import { mount } from "@vue/test-utils";
import mitt from "mitt";
import { createPinia, setActivePinia } from "pinia";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { defineComponent, reactive } from "vue";
import type { ScanStats } from "@/__generated__";
import platformApi from "@/services/api/platform";
import taskApi from "@/services/api/task";
import storeCollections from "@/stores/collections";
import storePlatforms, { type Platform } from "@/stores/platforms";
import storeRoms, { type SimpleRom } from "@/stores/roms";
import storeScanning from "@/stores/scanning";
import type { Events } from "@/types/emitter";
import { installScanLifecycle } from "./index";

// Minimal socket stand-in: records handlers so tests can fire events, and
// stays "connected" so `useSocketEvent` never tries to dial out.
const handlers = new Map<string, (payload: unknown) => void>();
vi.mock("@/services/socket", () => ({
  default: {
    connected: true,
    connect: vi.fn(),
    on: (event: string, handler: (payload: unknown) => void) => {
      handlers.set(event, handler);
    },
    off: vi.fn(),
  },
}));

vi.mock("@/services/api/task", () => ({
  default: { getTaskStatus: vi.fn() },
}));

// Platform lookups are incidental here: `getPlatform` for platforms the
// scanning store doesn't know yet, `getPlatforms` for the post-scan reconcile.
vi.mock("@/services/api/platform", () => ({
  default: {
    getPlatform: vi.fn(() => Promise.resolve({ data: { id: 1 } })),
    getPlatforms: vi.fn(() => Promise.resolve({ data: [] })),
  },
}));

// Reactive so the composable's `watch` on `authStore.user` fires when the
// user arrives after install, which is the real flow: AppLayout installs
// while /users/me is still in flight.
const authState = reactive({
  user: { id: 1, oauth_scopes: ["tasks.run"] } as {
    id: number;
    oauth_scopes: string[];
  } | null,
});
vi.mock("@/stores/auth", () => ({
  default: () => authState,
}));

const getTaskStatus = vi.mocked(taskApi.getTaskStatus);

/** Drain pending microtasks so the reconcile's promise chain has settled. */
const flushPromises = () => new Promise((resolve) => setTimeout(resolve, 0));

/** Outlast the handler's 100ms batching debounce for `scan:scanning_rom`. */
const drainRomBatch = () => new Promise((resolve) => setTimeout(resolve, 150));

function makeStats(overrides: Partial<ScanStats> = {}): ScanStats {
  return {
    total_platforms: 0,
    total_roms: 0,
    scanned_platforms: 0,
    new_platforms: 0,
    identified_platforms: 0,
    scanned_roms: 0,
    new_roms: 0,
    identified_roms: 0,
    scanned_firmware: 0,
    new_firmware: 0,
    updated_roms: 0,
    new_files: 0,
    ...overrides,
  };
}

function runningScanTask(stats: ScanStats | null) {
  return {
    task_name: "scan_platforms",
    task_id: "job-1",
    status: "started",
    task_type: "scan",
    created_at: null,
    enqueued_at: null,
    started_at: null,
    ended_at: null,
    meta: { scan_stats: stats },
  };
}

// The lifecycle uses `inject` and `onScopeDispose`, so it needs a host
// component instance. Tracked so `afterEach` can unmount it: the auth state
// is reactive and shared, so a leaked host would keep watching it and
// reconcile again during later tests.
let host: ReturnType<typeof mount> | null = null;

const emitter = mitt<Events>();

function install() {
  host = mount(
    defineComponent({
      setup() {
        installScanLifecycle();
        return () => null;
      },
    }),
    { global: { provide: { emitter } } },
  );
}

function fire(event: string, payload: unknown) {
  handlers.get(event)?.(payload);
}

describe("installScanLifecycle", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    handlers.clear();
    getTaskStatus.mockReset();
    getTaskStatus.mockResolvedValue({ data: [] } as never);
    authState.user = { id: 1, oauth_scopes: ["tasks.run"] };
  });

  afterEach(() => {
    host?.unmount();
    host = null;
  });

  it("treats a stats event as proof a scan is running", () => {
    install();
    const scanning = storeScanning();
    expect(scanning.scanning).toBe(false);

    fire("scan:update_stats", makeStats({ scanned_roms: 12 }));

    expect(scanning.scanning).toBe(true);
    expect(scanning.scanStats.scanned_roms).toBe(12);
  });

  it.each([
    ["scan:done", makeStats()],
    ["scan:done_ko", "disk gone"],
  ])("toasts %s only in the tab that started the scan", (event, payload) => {
    const shown = vi.fn();
    emitter.on("snackbarShow", shown);
    install();
    const scanning = storeScanning();

    scanning.setScanning(true);
    fire(event, payload);
    expect(shown).not.toHaveBeenCalled();

    scanning.setScanning(true);
    scanning.startedInThisTab = true;
    fire(event, payload);
    expect(shown).toHaveBeenCalledOnce();
    expect(scanning.startedInThisTab).toBe(false);

    emitter.off("snackbarShow", shown);
  });

  it("re-reads the virtual collections when the scan settles", () => {
    const collections = storeCollections();
    const refresh = vi
      .spyOn(collections, "refreshVirtualCollections")
      .mockResolvedValue([]);
    install();

    fire("scan:done", makeStats({ scanned_roms: 100 }));

    expect(refresh).toHaveBeenCalledTimes(1);
  });

  it("counts only the ROMs a scan added toward the platform's games", async () => {
    install();
    const platforms = storePlatforms();
    platforms.set([{ id: 1, rom_count: 2 } as Platform]);
    const scanningRom = (id: number, isNew: boolean) => ({
      id,
      platform_id: 1,
      platform_fs_slug: "n64",
      is_new: isNew,
    });

    fire("scan:scanning_rom", scanningRom(1, false));
    fire("scan:scanning_rom", scanningRom(2, false));
    fire("scan:scanning_rom", scanningRom(3, true));
    fire("scan:scanning_rom", scanningRom(3, true));
    await drainRomBatch();

    expect(platforms.get(1)?.rom_count).toBe(3);
  });

  it("counts a new ROM once when a platform event rebuilds the live log", async () => {
    install();
    const platforms = storePlatforms();
    platforms.set([{ id: 1, rom_count: 2 } as Platform]);
    const newRom = {
      id: 3,
      platform_id: 1,
      platform_fs_slug: "n64",
      platform_display_name: "Nintendo 64",
      is_new: true,
    };

    fire("scan:scanning_rom", newRom);
    await drainRomBatch();
    fire("scan:scanning_platform", {
      id: 1,
      name: "Nintendo 64",
      display_name: "Nintendo 64",
      slug: "n64",
      fs_slug: "n64",
      is_identified: true,
      new_firmware_count: 0,
    });
    fire("scan:scanning_rom", newRom);
    await drainRomBatch();

    expect(platforms.get(1)?.rom_count).toBe(3);
  });

  it("applies the last ROM batch before reconciling counts on scan:done", async () => {
    vi.mocked(platformApi.getPlatforms).mockResolvedValueOnce({
      data: [{ id: 1, rom_count: 3 }],
    } as never);
    install();
    const platforms = storePlatforms();
    platforms.set([{ id: 1, rom_count: 2 } as Platform]);

    fire("scan:scanning_rom", {
      id: 3,
      platform_id: 1,
      platform_fs_slug: "n64",
      is_new: true,
    });
    fire("scan:done", makeStats());
    await drainRomBatch();

    expect(platforms.get(1)?.rom_count).toBe(3);
  });

  it("puts only the ROMs a scan added at the top of the recent list", async () => {
    install();
    const roms = storeRoms();
    roms.setRecentRoms([{ id: 1, name: "Old" } as SimpleRom]);

    fire("scan:scanning_rom", {
      id: 1,
      name: "Rescanned",
      platform_id: 1,
      platform_fs_slug: "n64",
      is_new: false,
    });
    fire("scan:scanning_rom", {
      id: 2,
      platform_id: 1,
      platform_fs_slug: "n64",
      is_new: false,
    });
    fire("scan:scanning_rom", {
      id: 3,
      platform_id: 1,
      platform_fs_slug: "n64",
      is_new: true,
    });
    await drainRomBatch();

    expect(roms.recentRoms.map((r) => r.id)).toEqual([3, 1]);
    expect(roms.recentRoms[1].name).toBe("Rescanned");
  });

  it("reconciles with a running scan job on install", async () => {
    getTaskStatus.mockResolvedValue({
      data: [runningScanTask(makeStats({ scanned_roms: 40, total_roms: 100 }))],
    } as never);

    install();
    await flushPromises();

    const scanning = storeScanning();
    expect(scanning.scanning).toBe(true);
    expect(scanning.scanStats.scanned_roms).toBe(40);
    expect(scanning.scanStats.total_roms).toBe(100);
  });

  it("reconciles once the user arrives after install", async () => {
    // The real flow: AppLayout installs while /users/me is still in flight,
    // so `user` is null at install and the watch has to catch the arrival.
    authState.user = null;
    getTaskStatus.mockResolvedValue({
      data: [runningScanTask(makeStats({ scanned_roms: 7 }))],
    } as never);

    install();
    await flushPromises();
    expect(getTaskStatus).not.toHaveBeenCalled();

    authState.user = { id: 1, oauth_scopes: ["tasks.run"] };
    await flushPromises();

    expect(getTaskStatus).toHaveBeenCalledTimes(1);
    const scanning = storeScanning();
    expect(scanning.scanning).toBe(true);
    expect(scanning.scanStats.scanned_roms).toBe(7);
  });

  it("stays idle when no scan job is running", async () => {
    getTaskStatus.mockResolvedValue({
      data: [{ ...runningScanTask(makeStats()), status: "finished" }],
    } as never);

    install();
    await flushPromises();

    expect(storeScanning().scanning).toBe(false);
  });

  it("skips the reconcile without the tasks.run scope", async () => {
    authState.user = { id: 1, oauth_scopes: ["platforms.write"] };

    install();
    await flushPromises();

    expect(getTaskStatus).not.toHaveBeenCalled();
    expect(storeScanning().scanning).toBe(false);
  });

  it("does not resurrect a scan that ended while the reconcile was in flight", async () => {
    let resolveStatus!: (value: unknown) => void;
    getTaskStatus.mockReturnValue(
      new Promise((resolve) => {
        resolveStatus = resolve;
      }) as never,
    );

    install();
    fire("scan:done", makeStats({ scanned_roms: 100 }));
    resolveStatus({ data: [runningScanTask(makeStats({ scanned_roms: 40 }))] });
    await flushPromises();

    const scanning = storeScanning();
    expect(scanning.scanning).toBe(false);
    expect(scanning.scanStats.scanned_roms).toBe(100);
  });

  it("lets live stats win over the job's snapshot", async () => {
    let resolveStatus!: (value: unknown) => void;
    getTaskStatus.mockReturnValue(
      new Promise((resolve) => {
        resolveStatus = resolve;
      }) as never,
    );

    install();
    fire("scan:update_stats", makeStats({ scanned_roms: 90 }));
    resolveStatus({ data: [runningScanTask(makeStats({ scanned_roms: 40 }))] });
    await flushPromises();

    expect(storeScanning().scanStats.scanned_roms).toBe(90);
  });
});
