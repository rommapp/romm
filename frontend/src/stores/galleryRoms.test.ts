import { flushPromises } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import storeGalleryFilter from "@/stores/galleryFilter";
// Import after the mock so the store binds to the mocked rom API.
import storeGalleryRoms, {
  orderSupportsLetters,
  SELECT_ALL_PAGE_SIZE,
  type GalleryOrderKey,
} from "@/stores/galleryRoms";
import storePlatforms from "@/stores/platforms";
import { platformFixture } from "@/utils/platform.fixtures";
import { romFixture } from "@/utils/rom.fixtures";

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

function windowResponse(total: number | null = 1000, items: unknown[] = []) {
  return { data: { total, items, char_index: {}, rom_id_index: [] } };
}

// Id n sits at position n - 1, so a window's first id names its offset.
const IDS = Array.from({ length: 1000 }, (_, i) => i + 1);

async function withIdList() {
  getRoms.mockResolvedValueOnce({
    data: { total: IDS.length, items: [], char_index: {}, rom_id_index: IDS },
  });
  const store = storeGalleryRoms();
  await store.fetchInitialMetadata();
  getRoms.mockClear();
  return store;
}

// A window that returns every game it asked for.
function fullWindow(params: { romIds: number[] }) {
  return windowResponse(
    null,
    params.romIds.map((id) => ({ id })),
  );
}

function windowStarts(): number[] {
  return getRoms.mock.calls.map((c) => c[0].romIds[0]).sort((a, b) => a - b);
}

describe("galleryRoms windowed fetch", () => {
  beforeEach(() => {
    getRoms.mockReset();
    // Resolve the batched-apply frame yield synchronously so a window's
    // `finally` (which drains the queue) runs without waiting a real frame.
    vi.stubGlobal("requestAnimationFrame", (cb: FrameRequestCallback) => {
      cb(0);
      return 0;
    });
  });

  // The backend ranks a search by relevance only when no sort key is sent.
  it("sends an empty sort key when no sort is set", () => {
    getRoms.mockImplementation(() => Promise.resolve(windowResponse()));
    const store = storeGalleryRoms();
    store.setOrderBy(null);

    store.syncVisibleWindows([0]);

    expect(getRoms.mock.calls[0]![0].orderBy).toBe("");
  });

  it("collapses many visible positions into one request per 72-item window", async () => {
    const store = await withIdList();
    getRoms.mockImplementation((params) => Promise.resolve(fullWindow(params)));

    store.syncVisibleWindows([0, 5, 40, 71]);

    expect(getRoms).toHaveBeenCalledTimes(1);
    expect(getRoms.mock.calls[0]![0].romIds).toEqual(IDS.slice(0, 72));

    // Positions straddling the window boundary hit exactly two windows.
    await flushPromises();
    getRoms.mockClear();
    store.byPosition = new Map();
    store.loadedWindows = new Set();
    store.syncVisibleWindows([70, 72, 100]);
    expect(windowStarts()).toEqual([1, 73]);

    await flushPromises();
  });

  it("caps concurrent window fetches and drains the queue as slots free up", async () => {
    const store = await withIdList();
    const pending = new Map<number, () => void>();
    getRoms.mockImplementation((params: { romIds: number[] }) => {
      const d = deferred();
      pending.set(params.romIds[0] ?? 0, () => d.resolve(fullWindow(params)));
      return d.promise;
    });

    store.syncVisibleWindows([0, 72, 144, 216, 288, 360]);

    // Only MAX_CONCURRENT_WINDOWS (4) may be in flight; the rest are parked.
    expect(getRoms).toHaveBeenCalledTimes(4);

    for (const start of [1, 73, 145, 217]) {
      pending.get(start)?.();
    }
    await flushPromises();

    expect(getRoms).toHaveBeenCalledTimes(6);
    expect(windowStarts()).toEqual([1, 73, 145, 217, 289, 361]);
  });

  it("does not exceed the cap even as queued windows drain", async () => {
    let inFlight = 0;
    let peak = 0;
    const pending: (() => void)[] = [];
    getRoms.mockImplementation((params: { romIds: number[] }) => {
      inFlight++;
      peak = Math.max(peak, inFlight);
      const d = deferred();
      pending.push(() => d.resolve(fullWindow(params)));
      return d.promise.finally(() => {
        inFlight--;
      });
    });
    const store = await withIdList();
    getRoms.mockClear();

    store.syncVisibleWindows([0, 72, 144, 216, 288, 360, 432, 504]);

    // Drain by resolving windows one at a time; the peak in-flight count must
    // never pass the cap of 4.
    while (pending.length > 0) {
      pending.shift()?.();
      await flushPromises();
    }

    expect(peak).toBe(4);
    expect(getRoms).toHaveBeenCalledTimes(8);
  });

  // Surfaces that render none of the sidecars (the Settings "Missing" tab)
  // opt out of them, so the backend skips three whole-library scans per
  // request instead of computing two the caller throws away (issue #3992).
  it("lets the bootstrap opt out of the sidecars its caller does not render", async () => {
    getRoms.mockResolvedValue({
      data: { total: 12, items: [], char_index: {}, rom_id_index: [] },
    });
    const store = storeGalleryRoms();

    await store.fetchInitialMetadata({
      withCharIndex: false,
      withFilterValues: false,
      withRomIdIndex: false,
    });

    const params = getRoms.mock.calls[0]![0];
    expect(params.withCharIndex).toBe(false);
    expect(params.withFilterValues).toBe(false);
    expect(params.withRomIdIndex).toBe(false);
    // The total still lands: the backend falls back to a plain COUNT when
    // the id index is skipped, and that is all the caller needs to size its
    // virtual scroller.
    expect(store.total).toBe(12);
    expect(store.metadataLoaded).toBe(true);
  });

  it("requests every sidecar by default", async () => {
    getRoms.mockResolvedValue({
      data: { total: 1, items: [], char_index: {}, rom_id_index: [] },
    });
    const store = storeGalleryRoms();

    await store.fetchInitialMetadata();

    const params = getRoms.mock.calls[0]![0];
    expect(params.withCharIndex).toBeUndefined();
    expect(params.withFilterValues).toBeUndefined();
    expect(params.withRomIdIndex).toBeUndefined();
    expect(params.withTotal).toBeUndefined();
  });

  it("does not clobber the filter drawer when filter values are skipped", async () => {
    const galleryFilter = storeGalleryFilter();
    galleryFilter.setFilterGenres(["RPG", "Shooter"]);
    // Skipped sidecars come back empty but truthy, which would blank the
    // drawer if applied.
    getRoms.mockResolvedValue({
      data: {
        total: 3,
        items: [],
        char_index: {},
        rom_id_index: [],
        filter_values: { genres: [], platforms: [] },
      },
    });
    const store = storeGalleryRoms();

    await store.fetchInitialMetadata({ withFilterValues: false });

    expect(galleryFilter.filterGenres).toEqual(["RPG", "Shooter"]);
  });

  it("coerces null or missing filter_value lists from the API", async () => {
    // Publishers and developers are omitted, as an older API sends them.
    getRoms.mockResolvedValue({
      data: {
        total: 1,
        items: [],
        char_index: {},
        rom_id_index: [],
        filter_values: {
          genres: null,
          franchises: null,
          collections: null,
          companies: null,
          age_ratings: null,
          regions: null,
          languages: null,
          player_counts: null,
          tags: null,
          platforms: null,
        },
      },
    });
    storePlatforms().set([
      platformFixture({ slug: "snes", name: "Super Nintendo", rom_count: 1 }),
    ]);
    const galleryFilter = storeGalleryFilter();
    galleryFilter.setFilterGenres(["RPG"]);
    const store = storeGalleryRoms();

    await store.fetchInitialMetadata();

    // The bootstrap swallows errors, so this proves nothing threw midway.
    expect(store.metadataLoaded).toBe(true);
    expect(galleryFilter.filterPlatforms).toEqual([]);
    expect(galleryFilter.filterGenres).toEqual([]);
    expect(galleryFilter.filterDevelopers).toEqual([]);
    expect(galleryFilter.filterTags).toEqual([]);
  });

  describe("windows by id", () => {
    const ids = Array.from({ length: 200 }, (_, i) => 1000 + i);

    function bootstrapThen(window: (params: { romIds?: number[] }) => unknown) {
      getRoms.mockImplementation(
        (params: { limit?: number; romIds?: number[] }) =>
          params.limit === 1
            ? Promise.resolve({
                data: {
                  total: 200,
                  items: [],
                  char_index: {},
                  rom_id_index: ids,
                },
              })
            : Promise.resolve(window(params)),
      );
    }

    it("asks for its slice of the bootstrap's id list", async () => {
      // Arrange
      bootstrapThen(() => windowResponse(null));
      const store = storeGalleryRoms();
      await store.fetchInitialMetadata();

      // Act
      store.syncVisibleWindows([72]);
      await flushPromises();

      // Assert
      const windowCall = getRoms.mock.calls.find((c) => c[0].romIds);
      expect(Object.keys(windowCall?.[0] ?? {}).sort()).toEqual([
        "romIds",
        "signal",
      ]);
      expect(windowCall?.[0].romIds).toEqual(ids.slice(72, 144));
    });

    it("waits for the id list, then loads the window by id", async () => {
      // Arrange
      const boot = deferred();
      getRoms
        .mockImplementationOnce(() => boot.promise)
        .mockImplementation(() => Promise.resolve(windowResponse(null)));
      const store = storeGalleryRoms();

      // Act
      store.syncVisibleWindows([72]);
      const callsBeforeIds = getRoms.mock.calls.length;
      boot.resolve({
        data: { total: 200, items: [], char_index: {}, rom_id_index: ids },
      });
      await flushPromises();

      // Assert
      expect(callsBeforeIds).toBe(1);
      expect(getRoms.mock.calls[0]![0].limit).toBe(1);
      expect(getRoms.mock.calls[1]![0].romIds).toEqual(ids.slice(72, 144));
    });

    // A window short of ids answers by id; the stale-list refresh stays pending.
    function shortWindows(missing: number[]) {
      bootstrapThen((params) =>
        params.romIds
          ? windowResponse(
              null,
              params.romIds
                .filter((id) => !missing.includes(id))
                .map((id) => romFixture({ id })),
            )
          : deferred().promise,
      );
    }

    it("leaves a gap for an id the backend left out, without shifting the rest", async () => {
      // Arrange
      shortWindows([ids[73] ?? 0]);
      const store = storeGalleryRoms();
      await store.fetchInitialMetadata();

      // Act
      store.syncVisibleWindows([72]);
      await flushPromises();

      // Assert
      expect(store.byPosition.get(72)?.id).toBe(ids[72]);
      expect(store.byPosition.has(73)).toBe(false);
      expect(store.byPosition.get(74)?.id).toBe(ids[74]);
    });

    it("refreshes a stale id list once when a window comes back short", async () => {
      // Arrange
      shortWindows([ids[10] ?? 0, ids[80] ?? 0]);
      const store = storeGalleryRoms();
      await store.fetchInitialMetadata();

      // Act
      store.syncVisibleWindows([0, 72]);
      await flushPromises();

      // Assert
      const refreshes = getRoms.mock.calls.filter(
        (c) => !c[0].romIds && c[0].limit !== 1,
      );
      expect(refreshes).toHaveLength(1);
      expect(store.refreshing).toBe(true);
    });
  });

  it("does not mark a window loaded when the context is invalidated mid-apply", async () => {
    // Controllable frame yield so we can interleave a context switch between
    // the batched-apply's frames.
    const frames: FrameRequestCallback[] = [];
    vi.stubGlobal("requestAnimationFrame", (cb: FrameRequestCallback) => {
      frames.push(cb);
      return frames.length;
    });

    const store = await withIdList();
    const first = deferred();
    getRoms.mockImplementation(() => first.promise);

    store.syncVisibleWindows([0]);
    expect(getRoms).toHaveBeenCalledTimes(1);

    // More than one apply batch (APPLY_BATCH_SIZE = 8) so the apply parks on
    // a frame partway through.
    const items = IDS.slice(0, 16).map((id) => ({ id }));
    first.resolve({
      data: { total: null, items, char_index: {}, rom_id_index: [] },
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

    // The fresh context must be able to refetch offset 0: not skip it as
    // "already loaded" and strand its cards as permanent skeletons.
    getRoms.mockClear();
    getRoms.mockImplementation(() => deferred().promise);
    store.syncVisibleWindows([0]);
    expect(getRoms).toHaveBeenCalledTimes(1);
  });
});

describe("galleryRoms whole-result fetch", () => {
  beforeEach(() => {
    getRoms.mockReset();
  });

  it("pages through backend-capped pages until a short page", async () => {
    // A full page (the backend's limit cap) forces a second request.
    const fullPage = Array.from({ length: SELECT_ALL_PAGE_SIZE }, (_, i) => ({
      id: i,
    }));
    const lastPage = [
      { id: SELECT_ALL_PAGE_SIZE },
      { id: SELECT_ALL_PAGE_SIZE + 1 },
    ];
    getRoms.mockImplementation((params: { offset: number }) =>
      Promise.resolve(
        windowResponse(null, params.offset === 0 ? fullPage : lastPage),
      ),
    );
    const store = storeGalleryRoms();
    store.currentSearch = true;

    const roms = await store.fetchAllFilteredRoms();

    expect(roms).toHaveLength(SELECT_ALL_PAGE_SIZE + 2);
    expect(getRoms).toHaveBeenCalledTimes(2);
    expect(getRoms.mock.calls.map((c) => c[0].offset)).toEqual([
      0,
      SELECT_ALL_PAGE_SIZE,
    ]);
    // Whole-result pages skip every sidecar aggregation.
    expect(getRoms.mock.calls[0]![0]).toMatchObject({
      withCharIndex: false,
      withFilterValues: false,
      withRomIdIndex: false,
      withTotal: false,
    });
    // Loaded windows stay untouched: the result goes to the selection,
    // not into the sparse gallery cache.
    expect(store.byPosition.size).toBe(0);
  });

  it("returns null when the gallery context is invalidated mid-flight", async () => {
    const d = deferred();
    getRoms.mockReturnValue(d.promise);
    const store = storeGalleryRoms();
    store.currentSearch = true;

    const fetching = store.fetchAllFilteredRoms();
    store.invalidateWindows();
    d.resolve(windowResponse(null, [{ id: 1 }]));

    expect(await fetching).toBeNull();
    expect(store.selectingAll).toBe(false);
  });

  it("refuses to fetch off the gallery view", async () => {
    // Without a context the params would describe the whole library.
    const store = storeGalleryRoms();

    expect(await store.fetchAllFilteredRoms()).toBeNull();
    expect(getRoms).not.toHaveBeenCalled();
  });
});

describe("galleryRoms refresh", () => {
  beforeEach(() => {
    getRoms.mockReset();
  });

  function seedOldResult(store: ReturnType<typeof storeGalleryRoms>) {
    store.total = 2;
    store.metadataLoaded = true;
    store.byPosition = new Map([
      [0, romFixture({ id: 1 })],
      [1, romFixture({ id: 2 })],
    ]);
    store.loadedWindows = new Set([0]);
  }

  it("keeps the old result until the new page swaps in", async () => {
    const d = deferred();
    getRoms.mockReturnValue(d.promise);
    const store = storeGalleryRoms();
    seedOldResult(store);

    const refreshing = store.refreshResults();

    expect(store.refreshing).toBe(true);
    expect(store.total).toBe(2);
    expect(store.getRomAt(0)?.id).toBe(1);

    d.resolve(windowResponse(1, [{ id: 9 }]));

    expect(await refreshing).toBe(true);
    expect(store.refreshing).toBe(false);
    expect(store.total).toBe(1);
    expect(store.getRomAt(0)?.id).toBe(9);
    expect(store.getRomAt(1)).toBeNull();
    expect(store.loadedWindows).toEqual(new Set([0]));
  });

  it("fetches the page and its metadata in one request", async () => {
    getRoms.mockResolvedValue(windowResponse(1, [{ id: 9 }]));
    const store = storeGalleryRoms();

    await store.refreshResults();

    expect(getRoms).toHaveBeenCalledTimes(1);
    expect(getRoms.mock.calls[0]![0].withCharIndex).toBeUndefined();
    expect(getRoms.mock.calls[0]![0].offset).toBe(0);
  });

  it("fills the displayed result with its own request while refreshing", () => {
    getRoms.mockReturnValue(deferred().promise);
    const store = storeGalleryRoms();
    const filter = storeGalleryFilter();
    filter.searchTerm = "mario";
    store.syncVisibleWindows([0]);
    seedOldResult(store);
    store.total = 200;
    store.romIdIndex = IDS.slice(0, 200);
    getRoms.mockClear();

    filter.searchTerm = "zelda";
    void store.refreshResults();
    store.syncVisibleWindows([100]);

    const [refresh, window] = getRoms.mock.calls.map((c) => c[0]);
    expect(refresh.searchTerm).toBe("zelda");
    expect(window.romIds).toEqual(IDS.slice(72, 144));
  });

  it("keeps the displayed id list while refreshing", () => {
    getRoms.mockReturnValue(deferred().promise);
    const store = storeGalleryRoms();
    store.currentSearch = true;
    seedOldResult(store);
    store.romIdIndex = [1, 2];

    void store.refreshResults();

    expect(store.filteredRomIds).toEqual([1, 2]);
  });

  it("ends the old result's window fetches when the new one swaps in", async () => {
    const refresh = deferred();
    getRoms
      .mockReturnValueOnce(refresh.promise)
      .mockReturnValue(deferred().promise);
    const store = storeGalleryRoms();
    seedOldResult(store);
    store.total = 200;
    store.romIdIndex = IDS.slice(0, 200);

    const done = store.refreshResults();
    store.syncVisibleWindows([100]);
    const windowSignal: AbortSignal = getRoms.mock.calls[1]![0].signal;
    refresh.resolve(windowResponse(1, [{ id: 9 }]));
    await done;

    expect(windowSignal.aborted).toBe(true);
    expect(store.pendingWindows.size).toBe(0);
  });

  it("counts each result that replaces the displayed one", async () => {
    getRoms.mockResolvedValue(windowResponse(1, [{ id: 9 }]));
    const store = storeGalleryRoms();
    const start = store.resultEpoch;

    await store.refreshResults();
    expect(store.resultEpoch).toBe(start + 1);

    store.invalidateWindows();
    expect(store.resultEpoch).toBe(start + 2);

    // A superseded refresh replaces nothing.
    const stale = deferred();
    getRoms.mockReturnValueOnce(stale.promise);
    const older = store.refreshResults(() => {});
    await store.refreshResults();
    stale.resolve(windowResponse(1, [{ id: 1 }]));
    await older;
    expect(store.resultEpoch).toBe(start + 3);
  });

  it("builds requests from the live filters once no result is displayed", () => {
    getRoms.mockReturnValue(deferred().promise);
    const store = storeGalleryRoms();
    const filter = storeGalleryFilter();
    filter.searchTerm = "mario";
    store.syncVisibleWindows([0]);

    filter.searchTerm = "zelda";
    store.invalidateWindows();
    store.syncVisibleWindows([0]);

    expect(getRoms.mock.calls.map((c) => c[0].searchTerm)).toEqual([
      "mario",
      "zelda",
    ]);
  });

  it("lets a newer refresh supersede an older one", async () => {
    const first = deferred();
    const second = deferred();
    getRoms
      .mockReturnValueOnce(first.promise)
      .mockReturnValueOnce(second.promise);
    const store = storeGalleryRoms();

    const older = store.refreshResults();
    const newer = store.refreshResults();
    first.resolve(windowResponse(1, [{ id: 1 }]));
    second.resolve(windowResponse(1, [{ id: 2 }]));

    expect(await older).toBe(false);
    expect(await newer).toBe(true);
    expect(store.getRomAt(0)?.id).toBe(2);
  });

  it("runs the swap through the commit and skips it once superseded", async () => {
    getRoms.mockResolvedValueOnce(windowResponse(1, [{ id: 9 }]));
    const store = storeGalleryRoms();
    seedOldResult(store);
    let deferredApply: (() => boolean) | undefined;

    const older = store.refreshResults((apply) => {
      deferredApply = apply;
    });
    await flushPromises();
    getRoms.mockReturnValue(deferred().promise);
    void store.refreshResults();

    expect(deferredApply!()).toBe(false);
    expect(await older).toBe(false);
    expect(store.getRomAt(0)?.id).toBe(1);
  });

  it("falls back to skeletons when the refresh fails", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    getRoms
      .mockRejectedValueOnce(new Error("boom"))
      .mockReturnValue(deferred().promise);
    const store = storeGalleryRoms();
    seedOldResult(store);

    expect(await store.refreshResults()).toBe(false);

    expect(store.refreshing).toBe(false);
    expect(store.total).toBe(0);
    expect(store.byPosition.size).toBe(0);
    expect(store.initialFetching).toBe(true);
  });

  it("drops the old result when the gallery unmounts mid-refresh", () => {
    getRoms.mockReturnValue(deferred().promise);
    const store = storeGalleryRoms();
    seedOldResult(store);

    void store.refreshResults();
    store.abortInFlight();

    expect(store.refreshing).toBe(false);
    expect(store.metadataLoaded).toBe(false);
    expect(store.byPosition.size).toBe(0);
  });
});

describe("galleryRoms length filter", () => {
  beforeEach(() => {
    getRoms.mockReset();
    getRoms.mockImplementation(() => Promise.resolve(windowResponse()));
    vi.stubGlobal("requestAnimationFrame", (cb: FrameRequestCallback) => {
      cb(0);
      return 0;
    });
  });

  it("sends the hour bounds to the API as seconds", () => {
    storeGalleryFilter().setSelectedFilterLengthHours(5, 20);

    storeGalleryRoms().syncVisibleWindows([0]);

    expect(getRoms.mock.calls[0]![0].hltbMainStoryMin).toBe(5 * 3600);
    expect(getRoms.mock.calls[0]![0].hltbMainStoryMax).toBe(20 * 3600);
  });

  it("leaves an open end of the range unset", () => {
    storeGalleryFilter().setSelectedFilterLengthHours(null, 10);

    storeGalleryRoms().syncVisibleWindows([0]);

    expect(getRoms.mock.calls[0]![0].hltbMainStoryMin).toBeNull();
    expect(getRoms.mock.calls[0]![0].hltbMainStoryMax).toBe(10 * 3600);
  });
});

describe("galleryRoms relevance order", () => {
  beforeEach(() => {
    getRoms.mockReset();
    vi.stubGlobal("requestAnimationFrame", (cb: FrameRequestCallback) => {
      cb(0);
      return 0;
    });
  });

  async function answeredWith(charIndex: Record<string, number>, total = 5) {
    getRoms.mockResolvedValue({
      data: { total, items: [], char_index: charIndex, rom_id_index: [] },
    });
    setActivePinia(createPinia());
    const store = storeGalleryRoms();
    store.setOrderBy(null);
    await store.fetchInitialMetadata();
    return store;
  }

  it("reads an unset sort answered without letters as relevance", async () => {
    const store = await answeredWith({});

    expect(store.effectiveOrderBy).toBeNull();
  });

  it("reads an unset sort answered with letters as the name order", async () => {
    const store = await answeredWith({ a: 0 });

    expect(store.effectiveOrderBy).toBe("name");
  });

  it("keeps the answer through a refetch, so the controls don't flicker", async () => {
    const store = await answeredWith({});

    store.invalidateWindows();

    expect(store.effectiveOrderBy).toBeNull();
  });

  it("reads an empty result or a picked sort as no relevance", async () => {
    expect((await answeredWith({}, 0)).effectiveOrderBy).toBe("name");

    const sorted = await answeredWith({});
    sorted.setOrderBy("fs_size_bytes");
    expect(sorted.effectiveOrderBy).toBe("fs_size_bytes");
  });

  it("clears the direction along with the sort key", () => {
    const store = storeGalleryRoms();
    store.setOrderBy("name");
    store.setOrderDir("desc");

    store.setOrderBy(null);

    expect(store.orderBy).toBeNull();
    expect(store.orderDir).toBe("asc");
  });
});

describe("orderSupportsLetters", () => {
  // The backend indexes first letters off a text column only, so every other
  // order answers with an empty char_index. Spelling out every key means a new
  // sort key fails here until someone says which kind it is.
  const EXPECTED: Record<GalleryOrderKey, boolean> = {
    name: true,
    fs_name: true,
    platform_id: false,
    fs_size_bytes: false,
    created_at: false,
    updated_at: false,
    first_release_date: false,
    average_rating: false,
    hltb_main_story: false,
    last_played: false,
  };

  it.each(Object.entries(EXPECTED))("answers for %s", (key, expected) => {
    expect(orderSupportsLetters(key as GalleryOrderKey)).toBe(expected);
  });
});
