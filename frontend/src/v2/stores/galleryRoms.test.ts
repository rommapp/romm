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

  it("keeps the bootstrap char_index when the first window skips aggregations", async () => {
    getRoms.mockImplementation((params: { limit?: number }) => {
      // The bootstrap (limit 1) carries the char index; the follow-up
      // window skips it and the backend returns an empty (but truthy) {}.
      if (params.limit === 1) {
        return Promise.resolve({
          data: {
            total: 500,
            items: [],
            char_index: { A: 0, B: 10 },
            rom_id_index: [1, 2, 3],
          },
        });
      }
      return Promise.resolve(windowResponse(0, 500));
    });
    const store = storeGalleryRoms();

    await store.fetchInitialMetadata();
    expect(store.charIndex).toEqual({ A: 0, B: 10 });
    expect(store.metadataLoaded).toBe(true);

    // Window 0 loads with the aggregations skipped; its empty char_index
    // must not wipe what the bootstrap populated (the AlphaStrip bug).
    store.syncVisibleWindows([0]);
    await flushPromises();

    const windowCall = getRoms.mock.calls.find(
      (c) => c[0].withCharIndex === false,
    );
    expect(windowCall).toBeTruthy();
    // The follow-up window also opts out of the full-library id-index scan
    // the bootstrap already paid for.
    expect(windowCall?.[0].withRomIdIndex).toBe(false);
    expect(store.charIndex).toEqual({ A: 0, B: 10 });
  });

  it("does not mark a window loaded when the context is invalidated mid-apply", async () => {
    // Controllable frame yield so we can interleave a context switch between
    // the batched-apply's frames.
    const frames: FrameRequestCallback[] = [];
    vi.stubGlobal("requestAnimationFrame", (cb: FrameRequestCallback) => {
      frames.push(cb);
      return frames.length;
    });

    const first = deferred();
    getRoms.mockImplementation(() => first.promise);
    const store = storeGalleryRoms();

    store.syncVisibleWindows([0]);
    expect(getRoms).toHaveBeenCalledTimes(1);

    // More than one apply batch (APPLY_BATCH_SIZE = 8) so the apply parks on
    // a frame partway through.
    const items = Array.from({ length: 16 }, (_, i) => ({ id: i }));
    first.resolve({
      data: { total: 1000, items, char_index: {}, rom_id_index: [] },
    });
    await flushPromises();
    expect(frames.length).toBeGreaterThan(0);

    // Context switch (filter / sort / scan refresh) while the response is
    // still being applied.
    store.invalidateWindows();

    // Resume the parked frame(s): the apply sees it is no longer current and
    // bails without marking the window loaded.
    while (frames.length > 0) {
      frames.shift()?.(0);
      await flushPromises();
    }
    expect(store.loadedWindows.has(0)).toBe(false);

    // The fresh context must be able to refetch offset 0 — not skip it as
    // "already loaded" and strand its cards as permanent skeletons.
    getRoms.mockClear();
    getRoms.mockImplementation(() => deferred().promise);
    store.syncVisibleWindows([0]);
    expect(getRoms).toHaveBeenCalledTimes(1);
  });
});
