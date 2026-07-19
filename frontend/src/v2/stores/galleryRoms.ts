// galleryRoms (v2) — windowed/sparse store for the active gallery list.
//
// Replaces v1's `stores/roms.ts` for the gallery-list responsibility.
// What lives here:
//   - the gallery context (currentPlatform / Collection / Virtual / Smart),
//   - the total ROM count + per-letter offset table from the backend,
//   - a sparse `byPosition` map that holds whatever windows have been
//     fetched so far,
//   - book-keeping for in-flight / loaded / failed windows.
//
// Why a NEW store rather than extending v1:
//   v1 collapses pagination into `fetchRoms()` advancing a single
//   `fetchOffset`. v2 needs random-access window loads (driven by which
//   rows enter the virtualiser's viewport, including skeleton rows for
//   positions we've never touched). Forking lets v2 model that cleanly
//   while v1 stays frozen. Per the constitution, the v1 gallery-list
//   surface is annotated `@deprecated` with a pointer here.
//
// What does NOT live here:
//   - currentRom (lives in v1 `stores/roms`, GameDetails reads it),
//   - recentRoms / continuePlayingRoms (Home consumers stay on v1),
//   - selection state, order-by/order-dir,
//   These are still served by the v1 store; the v2 gallery view doesn't
//   need them.
import axios from "axios";
import { defineStore } from "pinia";
import type { SimpleRomSchema } from "@/__generated__/";
import type { CustomLimitOffsetPage_SimpleRomSchema_ as GetRomsResponse } from "@/__generated__/models/CustomLimitOffsetPage_SimpleRomSchema_";
import romApi from "@/services/api/rom";
import {
  type Collection,
  type SmartCollection,
  type VirtualCollection,
} from "@/stores/collections";
import storeGalleryFilter from "@/stores/galleryFilter";
import storePlatforms, { type Platform } from "@/stores/platforms";
import type { ExtractPiniaStoreType } from "@/types";

export type SimpleRom = SimpleRomSchema;

/** Sort keys the backend accepts for `/roms` ordering. The handler
 * resolves the column against `Rom`, then `RomMetadata`, then
 * `RomUser`, so this includes fields that aren't direct properties of
 * `SimpleRomSchema` (e.g. `first_release_date` lives on RomMetadata).
 * Keep this in sync with the columns the gallery surface exposes. */
export type GalleryOrderKey =
  | "name"
  | "fs_name"
  | "platform_id"
  | "fs_size_bytes"
  | "created_at"
  | "updated_at"
  | "first_release_date"
  | "average_rating"
  | "last_played";

type GalleryFilterStore = ExtractPiniaStoreType<typeof storeGalleryFilter>;

// Default window size — the backend's pagination limit. Smaller windows
// mean more round-trips but finer-grained fills; larger windows mean
// fewer requests but each one downloads more.
const WINDOW_SIZE = 72;

// In-flight `AbortController`s keyed by request: `window:${offset}`
// for a windowed fetch, `bootstrap` for the lightweight metadata
// bootstrap. Lives outside store state so Pinia doesn't
// try to proxy native abort objects (which break under reactivity).
// `invalidateWindows()` / `resetGallery()` abort every pending request,
// so a fast-typed search box or a platform-switch mid-load doesn't
// leave server work going for results we'll throw away.
const inFlightControllers = new Map<string, AbortController>();

// A failed window is only refetched when `fetchWindowAt` is called for it
// again, which for a static viewport (no scroll) never happens on its own.
// So a transient failure would strand up to `WINDOW_SIZE` visible cards as
// skeletons. To self-heal, a failed window schedules a bounded, backing-off
// retry; `retryTimers` holds the pending timeouts (keyed by offset) and
// `retryCounts` the attempts so far. Both are cleared by `abortAllInFlight`
// on any gallery-context switch so we never retry against a stale context.
const RETRY_BACKOFF_MS = 2000;
const MAX_WINDOW_RETRIES = 3;
const retryTimers = new Map<number, ReturnType<typeof setTimeout>>();
const retryCounts = new Map<number, number>();

function clearRetry(offset: number) {
  const timer = retryTimers.get(offset);
  if (timer !== undefined) clearTimeout(timer);
  retryTimers.delete(offset);
  retryCounts.delete(offset);
}

// Ceiling on concurrently in-flight window fetches. Windowing already
// collapses the old per-card request storm ~72x, but two or more users
// fast-scrolling a large library can still line up several windows at once
// against a backend that defaults to a single worker. This bounds how many
// hit the server simultaneously per client; windows over the ceiling wait in
// `queuedWindows` (FIFO) and drain as slots free up. Cleared by
// `abortAllInFlight` on any gallery-context switch.
const MAX_CONCURRENT_WINDOWS = 4;
const queuedWindows: number[] = [];

function clearQueue() {
  queuedWindows.length = 0;
}

function abortAllInFlight() {
  for (const ctrl of inFlightControllers.values()) ctrl.abort();
  inFlightControllers.clear();
  for (const timer of retryTimers.values()) clearTimeout(timer);
  retryTimers.clear();
  retryCounts.clear();
  clearQueue();
}

// Abort a single in-flight window fetch. The rejected request is caught
// as a cancel in `fetchWindowAt` (no `failedWindows` entry, no retry) and
// its `finally` clears the pending/controller bookkeeping.
function cancelWindow(offset: number) {
  const ctrl = inFlightControllers.get(`window:${offset}`);
  if (ctrl) ctrl.abort();
}

// Apply items to `byPosition` in row-sized batches with a rAF yield
// between batches. Each Map.set() invalidates Vue's per-key dep, and
// when many cards are in the viewport / overscan zone they all
// re-render in the same microtask flush — synchronously, on the main
// thread. With dozens of items landing back-to-back (initial window,
// or rapid-fire background fill), the flush can run >30ms and queued
// input events (AlphaStrip clicks especially) miss their frame.
//
// Yielding every `BATCH_SIZE` items lets the browser paint the new
// cards AND dispatch any pending input between batches. We pick 8 as
// the default — one row's worth — so a per-row dwell fetch (8 items)
// stays a single batch (no extra frames), while a 72-item window
// becomes 9 small batches that each fit comfortably in a frame.
const APPLY_BATCH_SIZE = 8;

function nextFrame(): Promise<void> {
  return new Promise((resolve) => {
    if (typeof requestAnimationFrame !== "undefined") {
      requestAnimationFrame(() => resolve());
    } else {
      setTimeout(resolve, 0);
    }
  });
}

async function applyItemsBatched(
  byPosition: Map<number, SimpleRom>,
  items: SimpleRom[],
  baseOffset: number,
  isStillRelevant: () => boolean,
): Promise<void> {
  for (let i = 0; i < items.length; i += APPLY_BATCH_SIZE) {
    if (!isStillRelevant()) return;
    const end = Math.min(i + APPLY_BATCH_SIZE, items.length);
    for (let j = i; j < end; j++) {
      byPosition.set(baseOffset + j, items[j]);
    }
    if (end < items.length) await nextFrame();
  }
}

interface State {
  currentPlatform: Platform | null;
  currentCollection: Collection | null;
  currentVirtualCollection: VirtualCollection | null;
  currentSmartCollection: SmartCollection | null;
  /** True while the global Search view owns the gallery. Distinct from
   * the platform/collection scopes (those carry an entity); search has
   * no entity, just a free-text term in `galleryFilter.searchTerm`.
   * Drives `onGalleryView` so `groupByMetaId` applies on Search too —
   * MissingGamesSection (Settings) intentionally leaves this `false`
   * so each missing file shows as its own row, never collapsed. */
  currentSearch: boolean;
  total: number;
  charIndex: Record<string, number>;
  romIdIndex: number[];
  byPosition: Map<number, SimpleRom>;
  loadedWindows: Set<number>;
  pendingWindows: Set<number>;
  failedWindows: Set<number>;
  // True until the very first metadata bootstrap (or fetchWindow(0))
  // resolves — view shows a skeleton hero/skeleton rows during this
  // phase.
  initialFetching: boolean;
  // True once total / charIndex / romIdIndex / filter_values have been
  // populated, either by the lightweight `fetchInitialMetadata()`
  // bootstrap or by `fetchWindowAt(0)`. Used to gate the initial
  // bootstrap dedup independently of `loadedWindows` (metadata
  // bootstrap doesn't load any window).
  metadataLoaded: boolean;
  // Order params — gallery-list scoped (separate from v1's localStorage
  // keys so v1/v2 don't fight over the same value).
  orderBy: GalleryOrderKey;
  orderDir: "asc" | "desc";
}

const defaults = (): State => ({
  currentPlatform: null,
  currentCollection: null,
  currentVirtualCollection: null,
  currentSmartCollection: null,
  currentSearch: false,
  total: 0,
  charIndex: {},
  romIdIndex: [],
  byPosition: new Map(),
  loadedWindows: new Set(),
  pendingWindows: new Set(),
  failedWindows: new Set(),
  initialFetching: false,
  metadataLoaded: false,
  orderBy: "name",
  orderDir: "asc",
});

function alignToWindow(offset: number): number {
  return Math.floor(offset / WINDOW_SIZE) * WINDOW_SIZE;
}

export default defineStore("v2GalleryRoms", {
  state: () => defaults(),

  getters: {
    onGalleryView: (state) =>
      !!(
        state.currentPlatform ||
        state.currentCollection ||
        state.currentVirtualCollection ||
        state.currentSmartCollection ||
        state.currentSearch
      ),
    /** True when at least the first window has loaded. */
    hasInitial: (state) => state.loadedWindows.size > 0,
  },

  actions: {
    setCurrentPlatform(platform: Platform | null) {
      this.currentPlatform = platform;
    },
    setCurrentCollection(collection: Collection | null) {
      this.currentCollection = collection;
    },
    setCurrentVirtualCollection(collection: VirtualCollection | null) {
      this.currentVirtualCollection = collection;
    },
    setCurrentSmartCollection(collection: SmartCollection | null) {
      this.currentSmartCollection = collection;
    },

    setOrderBy(key: GalleryOrderKey) {
      this.orderBy = key;
    },
    setOrderDir(dir: "asc" | "desc") {
      this.orderDir = dir;
    },

    /** Read a ROM at a position, or null if its window hasn't been
     * loaded yet. Returns null without triggering a fetch — fetching is
     * the view's responsibility (driven by row visibility). */
    getRomAt(position: number): SimpleRom | null {
      return this.byPosition.get(position) ?? null;
    },

    /** Find a loaded ROM by id, or null. Scans the sparse `byPosition`
     * window cache — used to seed the player hero cover synchronously on a
     * direct gallery→play so the shared-element morph has a target. */
    getRomById(id: number): SimpleRom | null {
      for (const rom of this.byPosition.values()) {
        if (rom.id === id) return rom;
      }
      return null;
    },

    /** Drop everything tied to the previous gallery context but keep
     * order-by / order-dir. Call before switching platform / collection
     * or when filters change. */
    resetGallery() {
      abortAllInFlight();
      this.currentPlatform = null;
      this.currentCollection = null;
      this.currentVirtualCollection = null;
      this.currentSmartCollection = null;
      this.currentSearch = false;
      this.total = 0;
      this.charIndex = {};
      this.romIdIndex = [];
      this.byPosition = new Map();
      this.loadedWindows = new Set();
      this.pendingWindows = new Set();
      this.failedWindows = new Set();
      this.initialFetching = false;
      this.metadataLoaded = false;
    },

    /** Drop the loaded windows but keep the gallery context — used when
     * search / filter changes within the same gallery and we need to
     * re-fetch from offset 0. */
    invalidateWindows() {
      abortAllInFlight();
      this.total = 0;
      this.charIndex = {};
      this.romIdIndex = [];
      this.byPosition = new Map();
      this.loadedWindows = new Set();
      this.pendingWindows = new Set();
      this.failedWindows = new Set();
      this.initialFetching = false;
      this.metadataLoaded = false;
    },

    _shouldGroupRoms(): boolean {
      const raw = localStorage.getItem("settings.groupRoms");
      return raw === null ? true : raw === "true";
    },

    _buildRequestParams(galleryFilter: GalleryFilterStore, offset: number) {
      // Determine platform IDs from the gallery context, falling back to
      // the gallery-filter store's platform multi-select.
      let platformIds: number[] | null = null;
      if (this.currentPlatform) {
        platformIds = [this.currentPlatform.id];
      } else if (galleryFilter.selectedPlatforms.length > 0) {
        platformIds = galleryFilter.selectedPlatforms.map((p) => p.id);
      } else if (galleryFilter.selectedPlatform) {
        platformIds = [galleryFilter.selectedPlatform.id];
      }
      return {
        searchTerm: galleryFilter.searchTerm,
        platformIds,
        collectionId: this.currentCollection?.id ?? null,
        virtualCollectionId: this.currentVirtualCollection?.id ?? null,
        smartCollectionId: this.currentSmartCollection?.id ?? null,
        limit: WINDOW_SIZE,
        offset,
        orderBy: this.orderBy,
        orderDir: this.orderDir,
        groupByMetaId: this._shouldGroupRoms() && this.onGalleryView,
        filterMatched: galleryFilter.filterMatched,
        filterFavorites: galleryFilter.filterFavorites,
        filterDuplicates: galleryFilter.filterDuplicates,
        filterPlayables: galleryFilter.filterPlayables,
        filterRA: galleryFilter.filterRA,
        filterSaves: galleryFilter.filterSaves,
        filterStates: galleryFilter.filterStates,
        filterSoundtrack: galleryFilter.filterSoundtrack,
        filterMissing: galleryFilter.filterMissing,
        filterVerified: galleryFilter.filterVerified,
        selectedGenres: galleryFilter.selectedGenres,
        selectedFranchises: galleryFilter.selectedFranchises,
        selectedCollections: galleryFilter.selectedCollections,
        selectedCompanies: galleryFilter.selectedCompanies,
        selectedAgeRatings: galleryFilter.selectedAgeRatings,
        selectedRegions: galleryFilter.selectedRegions,
        selectedLanguages: galleryFilter.selectedLanguages,
        selectedPlayerCounts: galleryFilter.selectedPlayerCounts,
        selectedMetadataProviders: galleryFilter.selectedMetadataProviders,
        selectedTags: galleryFilter.selectedTags,
        selectedStatuses: galleryFilter.selectedStatuses,
        genresLogic: galleryFilter.genresLogic,
        franchisesLogic: galleryFilter.franchisesLogic,
        collectionsLogic: galleryFilter.collectionsLogic,
        companiesLogic: galleryFilter.companiesLogic,
        ageRatingsLogic: galleryFilter.ageRatingsLogic,
        regionsLogic: galleryFilter.regionsLogic,
        languagesLogic: galleryFilter.languagesLogic,
        statusesLogic: galleryFilter.statusesLogic,
        playerCountsLogic: galleryFilter.playerCountsLogic,
        metadataProvidersLogic: galleryFilter.metadataProvidersLogic,
        tagsLogic: galleryFilter.tagsLogic,
      };
    },

    /** Apply the metadata side effects from a `getRoms` response —
     * total, char_index, rom_id_index, plus filter side panels (only on
     * first fetch). Shared by `fetchWindowAt(0)` and the lightweight
     * `fetchInitialMetadata()` bootstrap. */
    _applyMetadata(
      data: GetRomsResponse,
      galleryFilter: GalleryFilterStore,
      platformsStore: ReturnType<typeof storePlatforms>,
    ) {
      if (data.total !== null && data.total !== undefined) {
        this.total = data.total;
      }
      if (data.char_index) this.charIndex = data.char_index;
      if (data.rom_id_index) this.romIdIndex = data.rom_id_index;
      if (data.filter_values) {
        if (galleryFilter.filterPlatforms.length === 0) {
          galleryFilter.setFilterPlatforms(
            platformsStore.allPlatforms.filter((p) =>
              data.filter_values.platforms.includes(p.id),
            ),
          );
        }
        galleryFilter.setFilterCollections(data.filter_values.collections);
        galleryFilter.setFilterGenres(data.filter_values.genres);
        galleryFilter.setFilterFranchises(data.filter_values.franchises);
        galleryFilter.setFilterCompanies(data.filter_values.companies);
        galleryFilter.setFilterAgeRatings(data.filter_values.age_ratings);
        galleryFilter.setFilterRegions(data.filter_values.regions);
        galleryFilter.setFilterLanguages(data.filter_values.languages);
        galleryFilter.setFilterPlayerCounts(data.filter_values.player_counts);
        galleryFilter.setFilterTags(data.filter_values.tags);
      }
      this.metadataLoaded = true;
    },

    /** Lightweight bootstrap: fetch only the gallery's metadata (total,
     * char_index, rom_id_index, filter_values) without loading any
     * items. Sizes the virtualiser (via `total`) before any window
     * lands, so both layouts can render skeleton rows immediately and
     * then hydrate them through the viewport-driven `fetchWindowAt`
     * sync.
     *
     * The backend's `limit` minimum is 1, so we still pay for one
     * `SimpleRomSchema` build server-side, but the item is discarded
     * client-side. */
    async fetchInitialMetadata(): Promise<void> {
      if (this.metadataLoaded) return;
      if (this.initialFetching) return;

      this.initialFetching = true;

      const galleryFilter = storeGalleryFilter();
      const platformsStore = storePlatforms();
      const params = this._buildRequestParams(galleryFilter, 0);
      const ctrlKey = "bootstrap";
      const controller = new AbortController();
      inFlightControllers.set(ctrlKey, controller);

      try {
        const response = await romApi.getRoms({
          ...params,
          limit: 1,
          signal: controller.signal,
        });
        // Re-check that this bootstrap is still the relevant one —
        // invalidateWindows / resetGallery may have aborted us and a
        // newer bootstrap may have replaced our entry under the same key.
        // Identity comparison avoids applying stale metadata in that race.
        if (inFlightControllers.get(ctrlKey) !== controller) return;
        this._applyMetadata(response.data, galleryFilter, platformsStore);
      } catch (err) {
        if (axios.isCancel(err)) return;
        console.error("[v2GalleryRoms] bootstrap fetch failed", err);
      } finally {
        if (inFlightControllers.get(ctrlKey) === controller) {
          inFlightControllers.delete(ctrlKey);
          this.initialFetching = false;
        }
      }
    },

    /** Fetch the window that contains `position` (rounding down to the
     * window grid). Dedupes against pending / loaded windows. The very
     * first window also seeds `total` and `charIndex`. */
    async fetchWindowAt(position: number): Promise<void> {
      if (position < 0) return;
      const offset = alignToWindow(position);
      // Total is unknown for offset 0; for any non-initial offset, refuse
      // to fetch past total.
      if (this.total > 0 && offset >= this.total) return;
      if (this.loadedWindows.has(offset)) return;
      if (this.pendingWindows.has(offset)) return;

      // Concurrency cap: if every slot is busy, park this window and let a
      // settling fetch drain it (see `MAX_CONCURRENT_WINDOWS`). Offset 0 is
      // the initial window and is never queued (nothing is in flight yet).
      if (offset !== 0 && this.pendingWindows.size >= MAX_CONCURRENT_WINDOWS) {
        if (!queuedWindows.includes(offset)) queuedWindows.push(offset);
        return;
      }
      // Starting now — drop any queue entry so the drain loop won't re-run it.
      const queuedAt = queuedWindows.indexOf(offset);
      if (queuedAt !== -1) queuedWindows.splice(queuedAt, 1);

      this.pendingWindows.add(offset);
      this.failedWindows.delete(offset);
      if (offset === 0 && !this.metadataLoaded) this.initialFetching = true;

      const galleryFilter = storeGalleryFilter();
      const platformsStore = storePlatforms();
      const params = this._buildRequestParams(galleryFilter, offset);
      const ctrlKey = `window:${offset}`;
      const controller = new AbortController();
      inFlightControllers.set(ctrlKey, controller);

      try {
        const response = await romApi.getRoms({
          ...params,
          // Skip char index / filter-value aggregations when initial data is loaded
          ...(this.metadataLoaded
            ? { withCharIndex: false, withFilterValues: false }
            : {}),
          signal: controller.signal,
        });
        // Re-check identity: invalidateWindows / resetGallery / a context
        // switch may have run while we were waiting, and a fresh fetch may
        // already own this offset. Compare the controller rather than
        // `pendingWindows` membership (which a replacement fetch re-adds)
        // so we never apply stale data over the new context.
        if (inFlightControllers.get(ctrlKey) !== controller) return;

        const data = response.data;
        if (offset === 0) {
          this._applyMetadata(data, galleryFilter, platformsStore);
        } else if (data.total !== null && data.total !== undefined) {
          this.total = data.total;
        }

        // Place items at their absolute positions (offset .. offset + N).
        // We rely on Vue 3's reactive Map: `set(k, v)` triggers per-key
        // dependents. Earlier passes reassigned `this.byPosition` to a
        // new Map after each window which DEFEATED that — every
        // `getRomAt(p)` reader was invalidated, and the gallery
        // virtualItems computed (which iterates positions) had to
        // rebuild end-to-end on every window response. That blocked the
        // event loop hard enough to freeze the scroller. Mutating in
        // place keeps the dependents narrow: only positions that just
        // resolved trigger a re-render.
        //
        // Batched + frame-yielded: 72 sets in one microtask block the
        // main thread long enough that AlphaStrip clicks queued during
        // the flush miss their frame. `applyItemsBatched` pauses every
        // row (8 items) so input dispatches between paints.
        await applyItemsBatched(
          this.byPosition,
          data.items,
          offset,
          () => inFlightControllers.get(ctrlKey) === controller,
        );

        // A context switch during the frame-yielded apply may have
        // superseded us partway through. Marking the window loaded now would
        // leave it partially applied yet skipped by later syncs — permanent
        // skeletons for the fresh context. Bail unless we're still current.
        if (inFlightControllers.get(ctrlKey) !== controller) return;

        this.loadedWindows.add(offset);
        // Recovered — drop any retry bookkeeping for this window.
        clearRetry(offset);
      } catch (err) {
        // An explicit abort isn't a failure — keep `failedWindows`
        // clean so the window is eligible to refetch under the new
        // gallery context without the UI flagging it as broken.
        if (axios.isCancel(err)) return;
        // A late error for a window a newer fetch already owns isn't ours to
        // record or retry against the current context.
        if (inFlightControllers.get(ctrlKey) !== controller) return;
        this.failedWindows.add(offset);
        // Surface in console; UI keeps the skeletons in place until the
        // retry below (or a viewport / gallery-state change) refetches.
        console.error("[v2GalleryRoms] window fetch failed", offset, err);
        // Self-heal a stranded viewport: schedule a bounded, backing-off
        // refetch so a transient blip doesn't leave the window's cards as
        // skeletons until the user happens to scroll.
        const attempts = retryCounts.get(offset) ?? 0;
        if (attempts < MAX_WINDOW_RETRIES && !retryTimers.has(offset)) {
          retryCounts.set(offset, attempts + 1);
          const timer = setTimeout(
            () => {
              retryTimers.delete(offset);
              void this.fetchWindowAt(offset);
            },
            RETRY_BACKOFF_MS * (attempts + 1),
          );
          retryTimers.set(offset, timer);
        }
      } finally {
        // Only clear our own bookkeeping — a replacement fetch may already
        // own the key (see the identity checks above), and deleting it would
        // strand that request's window as a skeleton.
        if (inFlightControllers.get(ctrlKey) === controller) {
          inFlightControllers.delete(ctrlKey);
          this.pendingWindows.delete(offset);
          if (offset === 0) this.initialFetching = false;
        }
        // A slot freed up — start the next queued window, if any.
        this._drainWindowQueue();
      }
    },

    /** Start queued windows as in-flight slots free up. Called from a
     * window fetch's `finally`; the cap in `fetchWindowAt` guards the
     * ceiling, so this just feeds it the next parked offset. */
    _drainWindowQueue() {
      while (
        queuedWindows.length > 0 &&
        this.pendingWindows.size < MAX_CONCURRENT_WINDOWS
      ) {
        const next = queuedWindows.shift();
        if (next === undefined) break;
        if (this.loadedWindows.has(next) || this.pendingWindows.has(next)) {
          continue;
        }
        void this.fetchWindowAt(next);
      }
    },

    /** Reconcile in-flight window fetches with the currently visible
     * positions. Starts any window covering a visible position (deduped
     * inside `fetchWindowAt`) and aborts any in-flight or retry-pending
     * window that no longer covers one. Without the abort, scrolling
     * through a large library would leave every window it passed
     * downloading and applying in the background — the exact wasted
     * network / backend / render work this store exists to avoid on
     * low-power devices. Driven by the shell's debounced viewport sync. */
    syncVisibleWindows(positions: Iterable<number>) {
      const wanted = new Set<number>();
      for (const p of positions) {
        if (p < 0) continue;
        if (this.total > 0 && p >= this.total) continue;
        wanted.add(alignToWindow(p));
      }
      // Cancel windows that drifted out of view. Snapshot first: aborting
      // settles a fetch's `finally` (which mutates these sets) on a later
      // microtask, but iterate a copy to stay safe regardless.
      for (const offset of [...this.pendingWindows]) {
        if (!wanted.has(offset)) cancelWindow(offset);
      }
      for (const offset of [...retryTimers.keys()]) {
        if (!wanted.has(offset)) clearRetry(offset);
      }
      // Drop parked windows that scrolled out of view before getting a slot.
      for (let i = queuedWindows.length - 1; i >= 0; i--) {
        if (!wanted.has(queuedWindows[i])) queuedWindows.splice(i, 1);
      }
      for (const offset of wanted) {
        void this.fetchWindowAt(offset);
      }
    },

    /** Abort every in-flight window fetch + pending retry without wiping
     * the loaded cache. The shell calls this when the gallery unmounts so
     * navigating away mid-scroll doesn't leave downloads running; a
     * return to the same gallery still reuses `loadedWindows`. */
    abortInFlight() {
      abortAllInFlight();
      this.pendingWindows = new Set();
      this.initialFetching = false;
    },

    /** Apply (in place) an updated ROM to whatever position currently
     * holds it — used by edit / favourite / status flows. Mutating
     * via `set(pos, rom)` on the reactive Map triggers only the
     * dependents reading that specific position. */
    update(rom: SimpleRom) {
      for (const [pos, existing] of this.byPosition) {
        if (existing.id === rom.id) {
          this.byPosition.set(pos, rom);
          return;
        }
      }
    },

    /** Reconcile the gallery after ROMs are deleted. */
    remove(roms: SimpleRom[]) {
      if (this.currentPlatform) {
        const removedFromPlatform = roms.filter(
          (rom) => rom.platform_id === this.currentPlatform?.id,
        ).length;
        this.currentPlatform = {
          ...this.currentPlatform,
          rom_count: Math.max(
            0,
            this.currentPlatform.rom_count - removedFromPlatform,
          ),
        };
      }

      if (this.onGalleryView && roms.length > 0) {
        this.invalidateWindows();
        void this.fetchInitialMetadata();
      }
    },
  },
});
