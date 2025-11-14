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
import { type Platform } from "@/stores/platforms";
import type { ExtractPiniaStoreType } from "@/types";

type GalleryFilterStore = ExtractPiniaStoreType<typeof storeGalleryFilter>;

export type SimpleRom = SimpleRomSchema;
export type SearchRom = SearchRomSchema;
export type DetailedRom = DetailedRomSchema;
export const MAX_FETCH_LIMIT = 10000;

const orderByStorage = useLocalStorage("roms.orderBy", "name");
const orderDirStorage = useLocalStorage("roms.orderDir", "asc");

const defaultRomsState = {
  currentPlatform: null as Platform | null,
  currentCollection: null as Collection | null,
  currentVirtualCollection: null as VirtualCollection | null,
  currentSmartCollection: null as SmartCollection | null,
  currentRom: null as DetailedRom | null,
  _allRoms: [] as SimpleRom[],
  selectedIDs: new Set<number>(),
  recentRoms: [] as SimpleRom[],
  continuePlayingRoms: [] as SimpleRom[],
  lastSelectedIndex: -1,
  selectingRoms: false,
  fetchingRoms: false,
  initialSearch: false,
  fetchOffset: 0,
  fetchTotalRoms: 0,
  fetchLimit: 72,
  characterIndex: {} as Record<string, number>,
  selectedCharacter: null as string | null,
  romIdIndex: [] as number[],
  orderBy: orderByStorage.value as keyof SimpleRom,
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
    setCurrentCollection(collection: Collection | null) {
      this.currentCollection = collection;
    },
    setCurrentVirtualCollection(collection: VirtualCollection | null) {
      this.currentVirtualCollection = collection;
    },
    setCurrentSmartCollection(collection: SmartCollection | null) {
      this.currentSmartCollection = collection;
    },
    // Fetching multiple roms
    _buildRequestParams(galleryFilter: GalleryFilterStore) {
      return {
        ...galleryFilter.$state,
        platformId:
          this.currentPlatform?.id ??
          galleryFilter.selectedPlatform?.id ??
          null,
        collectionId: this.currentCollection?.id ?? null,
        virtualCollectionId: this.currentVirtualCollection?.id ?? null,
        smartCollectionId: this.currentSmartCollection?.id ?? null,
        limit: this.fetchLimit,
        offset: this.fetchOffset,
        orderBy: this.orderBy,
        orderDir: this.orderDir,
        groupByMetaId: this._shouldGroupRoms() && this.onGalleryView,
      };
    },
    _postFetchRoms(response: GetRomsResponse, concat: boolean) {
      const { items, offset, total, char_index, rom_id_index } = response;
      if (!concat || this.fetchOffset === 0) {
        this._allRoms = items;
      } else {
        this._allRoms = this._allRoms.concat(items);
      }

      // Update the offset and total roms in filtered database result
      if (offset !== null) this.fetchOffset = offset + this.fetchLimit;
      if (total !== null) this.fetchTotalRoms = total;

      // Set the character index for the current platform
      this.characterIndex = char_index;
      this.romIdIndex = rom_id_index;
    },
    async fetchRoms({
      galleryFilter,
      concat = true,
    }: {
      galleryFilter: GalleryFilterStore;
      concat?: boolean;
    }): Promise<SimpleRom[]> {
      if (this.fetchingRoms) return Promise.resolve([]);
      this.fetchingRoms = true;

      // Capture current request parameters to validate background updates
      const currentRequestParams = this._buildRequestParams(galleryFilter);

      return new Promise((resolve, reject) => {
        cachedApiService
          .getRoms(currentRequestParams, (response) => {
            if (concat && this.fetchOffset != 0) return;

            // Check if parameters have changed since the request was made
            const currentParams = this._buildRequestParams(galleryFilter);
            const paramsChanged =
              JSON.stringify(currentParams) !==
              JSON.stringify(currentRequestParams);
            if (paramsChanged) return;
            this._postFetchRoms(response, concat);
          })
          .then((response) => {
            this._postFetchRoms(response.data, concat);
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
    },
    remove(roms: SimpleRom[]) {
      this._allRoms = this._allRoms.filter((value) => {
        return !roms.find((rom) => {
          return rom.id === value.id;
        });
      });
    },
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
    setOrderBy(orderBy: keyof SimpleRom) {
      this.orderBy = orderBy;
      orderByStorage.value = orderBy;
    },
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
