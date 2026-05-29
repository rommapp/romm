import { useLocalStorage } from "@vueuse/core";
import { isNull, isUndefined } from "lodash";
import { defineStore } from "pinia";
import type {
  DetailedRomSchema,
  SimpleRomSchema,
  SearchRomSchema,
} from "@/__generated__/";
import type { CustomLimitOffsetPage_SimpleRomSchema_ as GetRomsResponse } from "@/__generated__/models/CustomLimitOffsetPage_SimpleRomSchema_";
import cachedApiService from "@/services/cache/api";
import {
  type Collection,
  type VirtualCollection,
  type SmartCollection,
} from "@/stores/collections";
import storeGalleryFilter from "@/stores/galleryFilter";
import storePlatforms from "@/stores/platforms";
import { type Platform } from "@/stores/platforms";
import type { ExtractPiniaStoreType } from "@/types";

type GalleryFilterStore = ExtractPiniaStoreType<typeof storeGalleryFilter>;
type PlatformsStore = ExtractPiniaStoreType<typeof storePlatforms>;

export type SimpleRom = SimpleRomSchema;
export type SearchRom = SearchRomSchema;
export type DetailedRom = DetailedRomSchema;

const orderByStorage = useLocalStorage("roms.orderBy", "name");
const orderDirStorage = useLocalStorage("roms.orderDir", "asc");

// NOTE on deprecation: the gallery-list responsibility (currentPlatform /
// Collection / Virtual / Smart, _allRoms, fetchOffset, fetchTotalRoms,
// characterIndex, romIdIndex, fetchRoms / resetPagination / reset, plus
// the order-by setters) has moved to the v2 store at
// `src/v2/stores/galleryRoms.ts` (windowed sparse loading). v1 keeps the
// originals for the frozen v1 UI; v2 imports the new store. Per-field
// @deprecated tags annotate the migrated surface so v1 cleanup is
// trivial when the time comes.
const defaultRomsState = {
  /** @deprecated v2: use `useGalleryRoms().currentPlatform` from
   * `@/v2/stores/galleryRoms`. */
  currentPlatform: null as Platform | null,
  /** @deprecated v2: use `useGalleryRoms().currentCollection`. */
  currentCollection: null as Collection | null,
  /** @deprecated v2: use `useGalleryRoms().currentVirtualCollection`. */
  currentVirtualCollection: null as VirtualCollection | null,
  /** @deprecated v2: use `useGalleryRoms().currentSmartCollection`. */
  currentSmartCollection: null as SmartCollection | null,
  currentRom: null as DetailedRom | null,
  /** @deprecated v2: rooms live in a sparse `byPosition` map on
   * `useGalleryRoms()`; iterate via `getRomAt(position)`. */
  _allRoms: [] as SimpleRom[],
  selectedIDs: new Set<number>(),
  recentRoms: [] as SimpleRom[],
  continuePlayingRoms: [] as SimpleRom[],
  lastSelectedIndex: -1,
  selectingRoms: false,
  /** @deprecated v2: per-window flags live on `useGalleryRoms()`
   * (`pendingWindows`, `initialFetching`). */
  fetchingRoms: false,
  initialSearch: false,
  /** @deprecated v2: window position is implicit in the sparse map;
   * read `useGalleryRoms().total` for the total count. */
  fetchOffset: 0,
  /** @deprecated v2: use `useGalleryRoms().total`. */
  fetchTotalRoms: 0,
  fetchLimit: 72,
  /** @deprecated v2: use `useGalleryRoms().charIndex`. */
  characterIndex: {} as Record<string, number>,
  selectedCharacter: null as string | null,
  /** @deprecated v2: use `useGalleryRoms().romIdIndex`. */
  romIdIndex: [] as number[],
  /** @deprecated v2: use `useGalleryRoms().orderBy` (gallery-scoped). */
  orderBy: orderByStorage.value as keyof SimpleRom,
  /** @deprecated v2: use `useGalleryRoms().orderDir`. */
  orderDir: orderDirStorage.value as "asc" | "desc",
};

export default defineStore("roms", {
  state: () => ({ ...defaultRomsState }),

  getters: {
    filteredRoms: (state) => state._allRoms,
    selectedRoms: (state) =>
      state._allRoms.filter((rom) => state.selectedIDs.has(rom.id)),
    onGalleryView: (state) =>
      !!(
        state.currentPlatform ||
        state.currentCollection ||
        state.currentVirtualCollection ||
        state.currentSmartCollection
      ),
  },

  actions: {
    _shouldGroupRoms(): boolean {
      return isNull(localStorage.getItem("settings.groupRoms"))
        ? true
        : localStorage.getItem("settings.groupRoms") === "true";
    },
    /** @deprecated v2: use `useGalleryRoms().setCurrentPlatform`. */
    setCurrentPlatform(platform: Platform | null) {
      this.currentPlatform = platform;
    },
    setCurrentRom(rom: DetailedRom) {
      this.currentRom = rom;
    },
    setRecentRoms(roms: SimpleRom[]) {
      this.recentRoms = roms;
    },
    setContinuePlayingRoms(roms: SimpleRom[]) {
      this.continuePlayingRoms = roms;
    },
    /** @deprecated v2: use `useGalleryRoms().setCurrentCollection`. */
    setCurrentCollection(collection: Collection | null) {
      this.currentCollection = collection;
    },
    /** @deprecated v2: use `useGalleryRoms().setCurrentVirtualCollection`. */
    setCurrentVirtualCollection(collection: VirtualCollection | null) {
      this.currentVirtualCollection = collection;
    },
    /** @deprecated v2: use `useGalleryRoms().setCurrentSmartCollection`. */
    setCurrentSmartCollection(collection: SmartCollection | null) {
      this.currentSmartCollection = collection;
    },
    // Fetching multiple roms
    _buildRequestParams(galleryFilter: GalleryFilterStore) {
      // Determine platform IDs
      let platformIds: number[] | null = null;

      // Prioritize currentPlatform if set, as it indicates a single platform view
      if (this.currentPlatform) {
        platformIds = [this.currentPlatform.id];
      } else if (galleryFilter.selectedPlatforms.length > 0) {
        // Otherwise, use multi-select platforms from filter
        platformIds = galleryFilter.selectedPlatforms.map((p) => p.id);
      } else if (galleryFilter.selectedPlatform) {
        // Fallback to single selected platform from filter
        platformIds = [galleryFilter.selectedPlatform.id];
      }

      const params = {
        searchTerm: galleryFilter.searchTerm,
        platformIds: platformIds,
        collectionId: this.currentCollection?.id ?? null,
        virtualCollectionId: this.currentVirtualCollection?.id ?? null,
        smartCollectionId: this.currentSmartCollection?.id ?? null,
        limit: this.fetchLimit,
        offset: this.fetchOffset,
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
        // Logic operators
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
      return params;
    },
    _postFetchRoms(
      response: GetRomsResponse,
      galleryFilter: GalleryFilterStore,
      platformsStore: PlatformsStore,
      concat: boolean,
    ) {
      const { items, offset, total, char_index, rom_id_index, filter_values } =
        response;
      if (!concat || this.fetchOffset === 0) {
        this._allRoms = items;
      } else {
        this._allRoms = this._allRoms.concat(items);
      }

      // Update the offset and total ROMs in filtered database result
      if (offset !== null) this.fetchOffset = offset + this.fetchLimit;
      if (total !== null) this.fetchTotalRoms = total;

      // Set the character index for the current platform
      this.characterIndex = char_index;
      this.romIdIndex = rom_id_index;

      // Only set the list of platforms on first fetch
      if (galleryFilter.filterPlatforms.length === 0) {
        galleryFilter.setFilterPlatforms(
          platformsStore.allPlatforms.filter((p) =>
            filter_values.platforms.includes(p.id),
          ),
        );
      }

      if (filter_values) {
        galleryFilter.setFilterCollections(filter_values.collections);
        galleryFilter.setFilterGenres(filter_values.genres);
        galleryFilter.setFilterFranchises(filter_values.franchises);
        galleryFilter.setFilterCompanies(filter_values.companies);
        galleryFilter.setFilterAgeRatings(filter_values.age_ratings);
        galleryFilter.setFilterRegions(filter_values.regions);
        galleryFilter.setFilterLanguages(filter_values.languages);
        galleryFilter.setFilterPlayerCounts(filter_values.player_counts);
      }
    },
    /** @deprecated v2: use `useGalleryRoms().fetchWindowAt(position)` for
     * windowed loading. The page-by-page model here is kept for v1 only. */
    async fetchRoms(concat = true): Promise<SimpleRom[]> {
      if (this.fetchingRoms) return Promise.resolve([]);
      this.fetchingRoms = true;

      const galleryFilterStore = storeGalleryFilter();
      const platformsStore = storePlatforms();

      // Capture current request parameters to validate background updates
      const currentRequestParams = this._buildRequestParams(galleryFilterStore);

      return new Promise((resolve, reject) => {
        cachedApiService
          .getRoms(currentRequestParams, (response) => {
            if (concat && this.fetchOffset != 0) return;

            // Check if parameters have changed since the request was made
            const currentParams = this._buildRequestParams(galleryFilterStore);
            const paramsChanged =
              JSON.stringify(currentParams) !==
              JSON.stringify(currentRequestParams);
            if (paramsChanged) return;
            this._postFetchRoms(
              response,
              galleryFilterStore,
              platformsStore,
              concat,
            );
          })
          .then((response) => {
            this._postFetchRoms(
              response.data,
              galleryFilterStore,
              platformsStore,
              concat,
            );
            resolve(response.data.items);
          })
          .catch((error) => {
            reject(error);
          })
          .finally(() => {
            this.fetchingRoms = false;
          });
      });
    },
    // Recent ROMs for home page
    async fetchRecentRoms(): Promise<SimpleRom[]> {
      const response = await cachedApiService.getRecentRoms((data) => {
        this.setRecentRoms(data.items);
      });
      const { items } = response.data;
      this.setRecentRoms(items);
      return items;
    },
    // Continue playing ROMs for home page
    async fetchContinuePlayingRoms(): Promise<SimpleRom[]> {
      const response = await cachedApiService.getRecentPlayedRoms((data) => {
        this.setContinuePlayingRoms(data.items);
      });
      const { items } = response.data;
      this.setContinuePlayingRoms(items);
      return items;
    },
    add(roms: SimpleRom[]) {
      this._allRoms = this._allRoms.concat(roms);
    },
    addToRecent(rom: SimpleRom) {
      this.recentRoms = [rom, ...this.recentRoms];
      cachedApiService.clearRecentRomsCache();
    },
    removeFromRecent(rom: SimpleRom) {
      this.recentRoms = this.recentRoms.filter((value) => value.id !== rom.id);
      cachedApiService.clearRecentRomsCache();
    },
    addToContinuePlaying(rom: SimpleRom) {
      this.continuePlayingRoms = [rom, ...this.continuePlayingRoms];
      cachedApiService.clearRecentPlayedRomsCache();
    },
    removeFromContinuePlaying(rom: SimpleRom) {
      this.continuePlayingRoms = this.continuePlayingRoms.filter(
        (value) => value.id !== rom.id,
      );
      cachedApiService.clearRecentPlayedRomsCache();
    },
    update(rom: SimpleRom) {
      this._allRoms = this._allRoms.map((value) =>
        value.id === rom.id ? rom : value,
      );
      this.recentRoms = this.recentRoms.map((value) =>
        value.id === rom.id ? rom : value,
      );
      this.continuePlayingRoms = this.continuePlayingRoms.map((value) =>
        value.id === rom.id ? rom : value,
      );
      // Keep `currentRom` in sync too — otherwise an optimistic mutation
      // on a SimpleRom from the gallery (status toggle from a GameCard
      // badge, favourite, …) leaves the detail view rendering stale
      // `rom_user` data, since the rom-route `beforeEnter` skips its
      // refetch when `currentRom.id` already matches. Spread merges the
      // SimpleRom shape over the cached DetailedRom so detailed-only
      // fields (metadatum, screenshots, related games, …) survive.
      if (this.currentRom?.id === rom.id) {
        this.currentRom = { ...this.currentRom, ...rom };
      }
    },
    remove(roms: SimpleRom[]) {
      this._allRoms = this._allRoms.filter((value) => {
        return !roms.find((rom) => {
          return rom.id === value.id;
        });
      });
    },
    /** @deprecated v2: use `useGalleryRoms().resetGallery()`. */
    reset() {
      this.currentPlatform = null;
      this.currentCollection = null;
      this.currentVirtualCollection = null;
      this.currentSmartCollection = null;
      this.currentRom = null;
      this._allRoms = [];
      this.selectedIDs = new Set<number>();
      this.lastSelectedIndex = -1;
      this.selectingRoms = false;
      this.fetchingRoms = false;
      this.initialSearch = false;
      this.characterIndex = {};
      this.selectedCharacter = null;
      this.romIdIndex = [];
      this.resetPagination();
    },
    /** @deprecated v2: use `useGalleryRoms().invalidateWindows()`. */
    resetPagination() {
      this.fetchOffset = 0;
      this.fetchTotalRoms = 0;
    },
    setSelection(roms: SimpleRom[]) {
      this.selectedIDs = new Set(roms.map((rom) => rom.id));
    },
    addToSelection(rom: SimpleRom) {
      this.selectedIDs.add(rom.id);
    },
    removeFromSelection(rom: SimpleRom) {
      this.selectedIDs.delete(rom.id);
    },
    updateLastSelected(index: number) {
      this.lastSelectedIndex = index;
    },
    setSelecting() {
      this.selectingRoms = !this.selectingRoms;
    },
    resetSelection() {
      this.selectedIDs = new Set<number>();
      this.lastSelectedIndex = -1;
    },
    /** @deprecated v2: use `useGalleryRoms().setOrderBy`. */
    setOrderBy(orderBy: keyof SimpleRom) {
      this.orderBy = orderBy;
      orderByStorage.value = orderBy;
    },
    /** @deprecated v2: use `useGalleryRoms().setOrderDir`. */
    setOrderDir(orderDir: "asc" | "desc") {
      this.orderDir = orderDir;
      orderDirStorage.value = orderDir;
    },
    setLimit(limit: number) {
      this.fetchLimit = limit;
    },
    isSimpleRom(rom: SimpleRom | SearchRom): rom is SimpleRom {
      return !isNull(rom.id) && !isUndefined(rom.id);
    },
  },
});
