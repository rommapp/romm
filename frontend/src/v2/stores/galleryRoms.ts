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

// In-flight `AbortController`s keyed by request — `window:${offset}`
// for the windowed initial fetch, `range:${offset}:${limit}` for the
// per-row dwell prefetch. Lives outside store state so Pinia doesn't
// try to proxy native abort objects (which break under reactivity).
// `invalidateWindows()` / `resetGallery()` abort every pending request,
// so a fast-typed search box or a platform-switch mid-load doesn't
// leave server work going for results we'll throw away.
const inFlightControllers = new Map<string, AbortController>();

function abortAllInFlight() {
  for (const ctrl of inFlightControllers.values()) ctrl.abort();
  inFlightControllers.clear();
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
  // populated — either by the lightweight `fetchInitialMetadata()`
  // bootstrap or by `fetchWindowAt(0)`. Used to gate the initial fetch
  // dedup independently of `loadedWindows` (metadata bootstrap doesn't
  // load any window).
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
      }
      this.metadataLoaded = true;
    },

    /** Lightweight bootstrap: fetch only the gallery's metadata (total,
     * char_index, rom_id_index, filter_values) without loading any
     * items. Use this when items will be hydrated lazily through the
     * per-card `fetchRomAt(p)` viewport sync — e.g. grid-mode galleries.
     *
     * The backend's `limit` minimum is 1, so we still pay for one
     * `SimpleRomSchema` build server-side, but we discard the item
     * client-side: every position (including 0) loads through the
     * unified per-card path so the staggered fade-in applies to the
     * first rows the same as the rest. List mode still wants
     * `fetchWindowAt(0)` because the table reads `byPosition` directly. */
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
          signal: controller.signal,
        });
        // Re-check that this window is still relevant — invalidateWindows
        // / resetGallery may have run while we were waiting.
        if (!this.pendingWindows.has(offset)) return;

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
        await applyItemsBatched(this.byPosition, data.items, offset, () =>
          this.pendingWindows.has(offset),
        );

        this.loadedWindows.add(offset);
      } catch (err) {
        // An explicit abort isn't a failure — keep `failedWindows`
        // clean so the window is eligible to refetch under the new
        // gallery context without the UI flagging it as broken.
        if (axios.isCancel(err)) return;
        this.failedWindows.add(offset);
        // Surface in console; UI keeps the skeletons in place — the
        // window can be retried by re-entering the row.
        console.error("[v2GalleryRoms] window fetch failed", offset, err);
      } finally {
        inFlightControllers.delete(ctrlKey);
        this.pendingWindows.delete(offset);
        if (offset === 0) this.initialFetching = false;
      }
    },

    /** Fetch an arbitrary `[offset, offset + limit)` range. Used by the
     * per-row dwell prefetch in the gallery views — instead of always
     * pulling the full 72-item window, a row asks for exactly its 8
     * positions, so visible rows can resolve in parallel and the user
     * sees covers stream in row-by-row.
     *
     * Skips the request when every position in the range is already
     * loaded; dedupes concurrent identical requests by (offset, limit)
     * key. The initial window — total / charIndex bootstrapping — still
     * goes through `fetchWindowAt(0)`. */
    /** Fetch the single ROM at `position` via `GET /roms/{id}/simple` —
     * the lightweight schema endpoint that skips the eager `user_saves`
     * / `user_states` / `user_screenshots` / `user_collections` /
     * `all_user_notes` arrays (those are 5 separate DB queries each;
     * dropping them takes the call from ~500ms to a typical by-id
     * lookup). The gallery card only needs the `has_*` indicator
     * flags + cover paths + platform info — all on `SimpleRomSchema`.
     * Detailed arrays are pulled on demand by the game-details page
     * or by quick-action dialogs (note editor, achievements panel)
     * when the user actually opens them.
     *
     * Requires `romIdIndex[position]` — populated by the first
     * `fetchWindowAt(0)` for the active gallery. Returns silently
     * if the index isn't loaded yet.
     *
     * Per-position `AbortController` allows the shell to cancel
     * fetches for cards that left the viewport before resolving.
     * `cancelFetchAt(position)` is the cancel side. */
    async fetchRomAt(position: number): Promise<void> {
      if (position < 0) return;
      if (this.total > 0 && position >= this.total) return;
      if (this.byPosition.has(position)) return;
      const romId = this.romIdIndex[position];
      if (!romId) return;

      const ctrlKey = `rom:${position}`;
      if (inFlightControllers.has(ctrlKey)) return;

      const controller = new AbortController();
      inFlightControllers.set(ctrlKey, controller);

      try {
        const response = await romApi.getRomSimple({
          romId,
          signal: controller.signal,
        });
        // Re-check that the shell still wants this position — a fast
        // scroll past + cancel races against the response landing.
        if (!inFlightControllers.has(ctrlKey)) return;
        this.byPosition.set(position, response.data);
      } catch (err) {
        if (axios.isCancel(err)) return;
        console.error("[v2GalleryRoms] rom fetch failed", position, romId, err);
      } finally {
        inFlightControllers.delete(ctrlKey);
      }
    },

    /** Cancel an in-flight per-position fetch — typically called by
     * the shell when a card leaves the viewport before its request
     * resolves. No-op if nothing is in flight for that position. */
    cancelFetchAt(position: number) {
      const ctrlKey = `rom:${position}`;
      const ctrl = inFlightControllers.get(ctrlKey);
      if (ctrl) {
        ctrl.abort();
        inFlightControllers.delete(ctrlKey);
      }
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

    /** Drop ROMs by id (delete flow). Positions become "holes" — kept
     * sparse rather than re-indexed; the next gallery refresh closes the
     * gaps. */
    remove(roms: SimpleRom[]) {
      const ids = new Set(roms.map((r) => r.id));
      for (const [pos, existing] of this.byPosition) {
        if (ids.has(existing.id)) this.byPosition.delete(pos);
      }
    },
  },
});
