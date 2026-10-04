import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { effectScope, type EffectScope } from "vue";
import { saveSyncMocks } from "@/test-utils/deviceSaveSync";
import { useDeviceSaveSync, type DeviceSaveSyncOptions } from "./index";

const mocks = vi.hoisted(() => ({ confirm: vi.fn() }));

vi.mock("vue-i18n");

vi.mock("@/stores/auth", () => ({
  default: () => ({ user: { id: 7 } }),
}));

vi.mock("@/v2/composables/useConfirm", () => ({
  useConfirm: () => mocks.confirm,
}));

vi.mock("@/v2/utils/saveSync", () => import("@/test-utils/deviceSaveSync"));

const ROM = { id: 1, fs_name_no_ext: "Game" };
const FILE = {
  slot: "a",
  fileName: "a.sav",
  bytes: new Uint8Array([1]),
  updatedAt: 1,
};

let scope: EffectScope | null = null;

function use(options: Partial<DeviceSaveSyncOptions> = {}) {
  scope = effectScope();
  return scope.run(() => useDeviceSaveSync({ emulator: "test", ...options }))!;
}

async function started(options: Partial<DeviceSaveSyncOptions> = {}) {
  const saveSync = use(options);
  await saveSync.prepare(ROM);
  saveSync.start();
  return saveSync;
}

function pagehide(persisted = false) {
  window.dispatchEvent(
    Object.assign(new Event("pagehide"), { persisted }) as PageTransitionEvent,
  );
}

beforeEach(() => {
  saveSyncMocks.prepare.mockResolvedValue([]);
  saveSyncMocks.capture.mockResolvedValue(undefined);
  saveSyncMocks.push.mockResolvedValue(true);
});

afterEach(() => {
  scope?.stop();
  scope = null;
  vi.useRealTimers();
});

describe("useDeviceSaveSync", () => {
  it("prepares as the signed-in user's device for its emulator", async () => {
    const saveSync = use();

    await saveSync.prepare(ROM, [FILE]);

    expect(saveSyncMocks.args).toEqual([ROM, 7, "test"]);
    expect(saveSyncMocks.prepare).toHaveBeenCalledWith([FILE]);
    expect(saveSync.isActive()).toBe(false);
  });

  it("pushes nothing until started", async () => {
    const saveSync = use();
    await saveSync.prepare(ROM);

    expect(await saveSync.push()).toBe(true);
    expect(saveSyncMocks.push).not.toHaveBeenCalled();
  });

  it("captures what it reads before each push", async () => {
    const read = vi.fn().mockResolvedValue([FILE]);
    const saveSync = await started({ read });

    expect(await saveSync.push()).toBe(true);
    expect(saveSyncMocks.capture).toHaveBeenCalledWith([FILE]);
    expect(saveSyncMocks.push).toHaveBeenCalledOnce();
  });

  it("joins a push already in flight, and flushes after it", async () => {
    let release!: (files: (typeof FILE)[]) => void;
    const read = vi
      .fn()
      .mockReturnValueOnce(new Promise((resolve) => (release = resolve)))
      .mockResolvedValue([FILE]);
    const saveSync = await started({ read });

    const first = saveSync.push();
    expect(saveSync.push()).toBe(first);
    const flushed = saveSync.flush();
    release([]);

    expect(await flushed).toBe(true);
    expect(read).toHaveBeenCalledTimes(2);
  });

  it("reports a failed push as false", async () => {
    vi.spyOn(console, "error").mockImplementation(() => undefined);
    const saveSync = await started({
      read: vi.fn().mockRejectedValue(new Error("blocked")),
    });

    expect(await saveSync.push()).toBe(false);
  });

  it("polls only while running", async () => {
    vi.useFakeTimers();
    const read = vi.fn().mockResolvedValue([]);
    const saveSync = await started({ read });

    await vi.advanceTimersByTimeAsync(5000);
    expect(read).toHaveBeenCalledOnce();

    saveSync.pause();
    await vi.advanceTimersByTimeAsync(5000);
    expect(read).toHaveBeenCalledOnce();
  });

  it("keeps polled saves here, uploading them at most once per interval", async () => {
    vi.useFakeTimers();
    const read = vi.fn().mockResolvedValue([FILE]);
    const saveSync = await started({ read, uploadIntervalMs: 60_000 });

    await vi.advanceTimersByTimeAsync(55_000);
    expect(saveSyncMocks.capture).toHaveBeenCalledTimes(11);
    expect(saveSyncMocks.push).not.toHaveBeenCalled();

    await vi.advanceTimersByTimeAsync(5000);
    expect(saveSyncMocks.push).toHaveBeenCalledOnce();

    expect(await saveSync.flush()).toBe(true);
    expect(saveSyncMocks.push).toHaveBeenCalledTimes(2);
  });

  it("sends captured changes as the page goes away", async () => {
    await started();

    pagehide(true);

    expect(saveSyncMocks.pushOnUnload).toHaveBeenCalledOnce();
  });

  it("captures what the player holds as the page goes away", async () => {
    await started({ readOnUnload: () => [FILE] });

    pagehide(true);
    expect(saveSyncMocks.captureOnUnload).not.toHaveBeenCalled();

    pagehide();
    expect(saveSyncMocks.captureOnUnload).toHaveBeenCalledWith([FILE]);
  });

  it("does nothing on the way out once stopped", async () => {
    const saveSync = await started();

    saveSync.stop();
    pagehide();

    expect(saveSyncMocks.pushOnUnload).not.toHaveBeenCalled();
  });

  it("asks before discarding unsynced saves", async () => {
    mocks.confirm.mockResolvedValue(true);
    const saveSync = use();

    expect(await saveSync.confirmDiscard()).toBe(true);
    expect(mocks.confirm).toHaveBeenCalledWith(
      expect.objectContaining({ tone: "danger" }),
    );
  });
});
