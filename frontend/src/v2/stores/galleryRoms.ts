// galleryRoms (v2) — sparse store for the active gallery list.
//
// Replaces v1's `stores/roms.ts` for the gallery-list responsibility.
// What lives here:
//   - the gallery context (currentPlatform / Collection / Virtual / Smart),
//   - the total ROM count + per-letter offset table + id index from the
//     backend,
//   - a sparse `byPosition` map that holds whatever positions have been
//     hydrated so far (per-card, driven by row visibility),
//   - book-keeping for in-flight per-card fetches.
//
// Why a NEW store rather than extending v1:
//   v1 collapses pagination into `fetchRoms()` advancing a single
//   `fetchOffset`. v2 needs random-access per-card loads (driven by which
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

// Default page size — the backend's pagination limit, used by the
// metadata bootstrap's request params.
const WINDOW_SIZE = 72;

// In-flight `AbortController`s keyed by request: `rom:${position}` for a
// per-card hydration fetch, `bootstrap` for the lightweight metadata
// bootstrap. Lives outside store state so Pinia doesn't try to proxy
// native abort objects (which break under reactivity).
// `invalidateWindows()` / `resetGallery()` abort every pending request,
// so a fast-typed search box or a platform-switch mid-load doesn't
// leave server work going for results we'll throw away.
const inFlightControllers = new Map<string, AbortController>();

function abortAllInFlight() {
  for (const ctrl of inFlightControllers.values()) ctrl.abort();
  inFlightControllers.clear();
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
  // True until the very first metadata bootstrap resolves — view shows a
  // skeleton hero/skeleton rows during this phase.
  initialFetching: boolean;
  // True once total / charIndex / romIdIndex / filter_values have been
  // populated by the lightweight `fetchInitialMetadata()` bootstrap.
  // Gates the bootstrap dedup and the per-card hydration (which needs
  // `romIdIndex` before it can resolve a position to a rom id).
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
  initialFetching: false,
  metadataLoaded: false,
  orderBy: "name",
  orderDir: "asc",
});

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
     * total, char_index, rom_id_index, plus filter side panels. Used by
     * the lightweight `fetchInitialMetadata()` bootstrap. */
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
     * items. Sizes the virtualiser (via `total`) so both layouts can
     * render skeleton rows immediately, then hydrate each visible
     * position through the viewport-driven per-card `fetchRomAt(p)` sync.
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

    /** Fetch the single ROM at `position` via `GET /roms/{id}/simple` —
     * the lightweight schema endpoint that skips the eager `user_saves`
     * / `user_states` / `user_screenshots` / `user_collections` /
     * `all_user_notes` arrays. The gallery card only needs the `has_*`
     * indicator flags + cover paths + platform info — all on
     * `SimpleRomSchema`. Detailed arrays are pulled on demand by the
     * game-details page or by quick-action dialogs (note editor,
     * achievements panel) when the user actually opens them.
     *
     * Requires `romIdIndex[position]` — populated by the
     * `fetchInitialMetadata()` bootstrap for the active gallery. Returns
     * silently if the index isn't loaded yet.
     *
     * Per-position `AbortController` allows the shell to cancel fetches
     * for cards that left the viewport before resolving.
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
        // Re-check that we're still the relevant request for this key — a
        // fast scroll-past + cancel + re-enter can replace our controller
        // with a newer one under the same key before we land. Identity
        // comparison keeps us from applying our stale response over it.
        if (inFlightControllers.get(ctrlKey) !== controller) return;
        this.byPosition.set(position, response.data);
      } catch (err) {
        if (axios.isCancel(err)) return;
        console.error("[v2GalleryRoms] rom fetch failed", position, romId, err);
      } finally {
        // Only clear our own entry — a replacement request may already own
        // the key (see the identity check above), and deleting it would
        // strand that request's response and leave the card a skeleton.
        if (inFlightControllers.get(ctrlKey) === controller) {
          inFlightControllers.delete(ctrlKey);
        }
      }
    },

    /** Cancel an in-flight per-position fetch — typically called by the
     * shell when a card leaves the viewport before its request resolves.
     * No-op if nothing is in flight for that position. */
    cancelFetchAt(position: number) {
      const ctrlKey = `rom:${position}`;
      const ctrl = inFlightControllers.get(ctrlKey);
      if (ctrl) {
        ctrl.abort();
        inFlightControllers.delete(ctrlKey);
      }
    },

    /** Abort every in-flight per-card fetch without wiping the hydrated
     * cache. The shell calls this when the gallery unmounts so navigating
     * away mid-scroll doesn't leave requests running; a return to the
     * same gallery still reuses whatever `byPosition` already holds. */
    abortInFlight() {
      abortAllInFlight();
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
