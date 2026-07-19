import { flushPromises } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
// Import after the mock so the store binds to the mocked rom API.
import storeGalleryRoms from "@/v2/stores/galleryRoms";

const { getRoms } = vi.hoisted(() => ({ getRoms: vi.fn() }));

vi.mock("@/services/api/rom", () => ({
  default: { getRoms },
}));

interface Deferred {
  promise: Promise<unknown>;
  resolve: (value: unknown) => void;
}

function deferred(): Deferred {
  let resolve!: (value: unknown) => void;
  const promise = new Promise<unknown>((r) => {
    resolve = r;
  });
  return { promise, resolve };
}

function windowResponse(offset: number, total = 1000) {
  return { data: { total, items: [], char_index: {}, rom_id_index: [] } };
}

describe("galleryRoms windowed fetch", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    getRoms.mockReset();
    // Resolve the batched-apply frame yield synchronously so a window's
    // `finally` (which drains the queue) runs without waiting a real frame.
    vi.stubGlobal("requestAnimationFrame", (cb: FrameRequestCallback) => {
      cb(0);
      return 0;
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("collapses many visible positions into one request per 72-item window", async () => {
    getRoms.mockImplementation((params: { offset: number }) =>
      Promise.resolve(windowResponse(params.offset)),
    );
    const store = storeGalleryRoms();

    // Every position falls inside the first 72-item window.
    store.syncVisibleWindows([0, 5, 40, 71]);

    expect(getRoms).toHaveBeenCalledTimes(1);
    expect(getRoms.mock.calls[0][0].offset).toBe(0);

    // Positions straddling the window boundary hit exactly two windows.
    await flushPromises();
    getRoms.mockClear();
    store.byPosition = new Map();
    store.loadedWindows = new Set();
    store.syncVisibleWindows([70, 72, 100]);
    const offsets = getRoms.mock.calls
      .map((c) => c[0].offset)
      .sort((a, b) => a - b);
    expect(offsets).toEqual([0, 72]);

    await flushPromises();
  });

  it("caps concurrent window fetches and drains the queue as slots free up", async () => {
    const pending = new Map<number, Deferred>();
    getRoms.mockImplementation((params: { offset: number }) => {
      const d = deferred();
      pending.set(params.offset, d);
      return d.promise;
    });
    const store = storeGalleryRoms();

    // Six distinct windows want to load at once (0, 72, ..., 360).
    store.syncVisibleWindows([0, 72, 144, 216, 288, 360]);

    // Only MAX_CONCURRENT_WINDOWS (4) may be in flight; the rest are parked.
    expect(getRoms).toHaveBeenCalledTimes(4);

    // Resolve the four in-flight windows; each freed slot pulls one from the
    // queue until all six have run.
    for (const offset of [0, 72, 144, 216]) {
      pending.get(offset)?.resolve(windowResponse(offset));
    }
    await flushPromises();

    expect(getRoms).toHaveBeenCalledTimes(6);
    const offsets = getRoms.mock.calls
      .map((c) => c[0].offset)
      .sort((a, b) => a - b);
    expect(offsets).toEqual([0, 72, 144, 216, 288, 360]);
  });

  it("does not exceed the cap even as queued windows drain", async () => {
    let inFlight = 0;
    let peak = 0;
    const pending: Deferred[] = [];
    getRoms.mockImplementation(() => {
      inFlight++;
      peak = Math.max(peak, inFlight);
      const d = deferred();
      pending.push(d);
      return d.promise.finally(() => {
        inFlight--;
      });
    });
    const store = storeGalleryRoms();

    store.syncVisibleWindows([0, 72, 144, 216, 288, 360, 432, 504]);

    // Drain by resolving windows one at a time; the peak in-flight count must
    // never pass the cap of 4.
    while (pending.length > 0) {
      pending.shift()?.resolve(windowResponse(0));
      await flushPromises();
    }

    expect(peak).toBe(4);
    expect(getRoms).toHaveBeenCalledTimes(8);
  });
});
