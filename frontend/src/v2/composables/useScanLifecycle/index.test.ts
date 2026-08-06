import { mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { defineComponent, nextTick } from "vue";
import type { ScanStats } from "@/__generated__";
import taskApi from "@/services/api/task";
import storeScanning from "@/stores/scanning";
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

const authState = {
  user: { id: 1, oauth_scopes: ["tasks.run"] } as {
    id: number;
    oauth_scopes: string[];
  } | null,
};
vi.mock("@/stores/auth", () => ({
  default: () => authState,
}));

const getTaskStatus = vi.mocked(taskApi.getTaskStatus);

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
// component instance.
function install() {
  mount(
    defineComponent({
      setup() {
        installScanLifecycle();
        return () => null;
      },
    }),
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

  it("treats a stats event as proof a scan is running", () => {
    install();
    const scanning = storeScanning();
    expect(scanning.scanning).toBe(false);

    fire("scan:update_stats", makeStats({ scanned_roms: 12 }));

    expect(scanning.scanning).toBe(true);
    expect(scanning.scanStats.scanned_roms).toBe(12);
  });

  it("reconciles with a running scan job on install", async () => {
    getTaskStatus.mockResolvedValue({
      data: [runningScanTask(makeStats({ scanned_roms: 40, total_roms: 100 }))],
    } as never);

    install();
    await nextTick();
    await nextTick();

    const scanning = storeScanning();
    expect(scanning.scanning).toBe(true);
    expect(scanning.scanStats.scanned_roms).toBe(40);
    expect(scanning.scanStats.total_roms).toBe(100);
  });

  it("stays idle when no scan job is running", async () => {
    getTaskStatus.mockResolvedValue({
      data: [{ ...runningScanTask(makeStats()), status: "finished" }],
    } as never);

    install();
    await nextTick();
    await nextTick();

    expect(storeScanning().scanning).toBe(false);
  });

  it("skips the reconcile without the tasks.run scope", async () => {
    authState.user = { id: 1, oauth_scopes: ["platforms.write"] };

    install();
    await nextTick();

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
    await nextTick();
    await nextTick();

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
    await nextTick();
    await nextTick();

    expect(storeScanning().scanStats.scanned_roms).toBe(90);
  });
});
