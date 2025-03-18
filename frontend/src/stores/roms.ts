import type { SearchRomSchema } from "@/__generated__";
import type { DetailedRomSchema, SimpleRomSchema } from "@/__generated__/";
import romApi from "@/services/api/rom";
import { type Collection, type VirtualCollection } from "@/stores/collections";
import storeGalleryFilter from "@/stores/galleryFilter";
import { type Platform } from "@/stores/platforms";
import type { ExtractPiniaStoreType } from "@/types";
import { groupBy, isNull, isUndefined, uniqBy } from "lodash";
import { nanoid } from "nanoid";
import { defineStore } from "pinia";

type GalleryFilterStore = ExtractPiniaStoreType<typeof storeGalleryFilter>;

export type SimpleRom = SimpleRomSchema;
export type DetailedRom = DetailedRomSchema;

const defaultRomsState = {
  currentPlatform: null as Platform | null,
  currentCollection: null as Collection | null,
  currentVirtualCollection: null as VirtualCollection | null,
  currentRom: null as DetailedRom | null,
  allRoms: [] as SimpleRom[],
  _grouped: [] as SimpleRom[],
  _selectedIDs: new Set<number>(),
  recentRoms: [] as SimpleRom[],
  continuePlayingRoms: [] as SimpleRom[],
  lastSelectedIndex: -1,
  selectingRoms: false,
  fetchingRoms: false,
  fetchLimit: 72,
  fetchOffset: 0,
  fetchTotalRoms: 0,
};

export default defineStore("roms", {
  state: () => ({ ...defaultRomsState }),

  getters: {
    filteredRoms: (state) => state._grouped,
    selectedRoms: (state) =>
      state._grouped.filter((rom) => state._selectedIDs.has(rom.id)),
  },

  actions: {
    _shouldGroupRoms(): boolean {
      return isNull(localStorage.getItem("settings.groupRoms"))
        ? true
        : localStorage.getItem("settings.groupRoms") === "true";
    },
    _getGroupedRoms(roms: SimpleRom[]): SimpleRom[] {
      // Group roms by external id.
      return Object.values(
        groupBy(
          roms,
          (game) =>
            // If external id is null, generate a random id so that the roms are not grouped
            game.igdb_id || game.moby_id || game.ss_id || nanoid(),
        ),
      ).map((games) => {
        // Find the index of the game where the 'rom_user' property has 'is_main_sibling' set to true.
        return games.find((game) => game.rom_user?.is_main_sibling) || games[0];
      });
    },
    _reorder() {
      // Sort roms by comparator string
      this.allRoms = uniqBy(this.allRoms, "id").sort((a, b) => {
        return a.sort_comparator.localeCompare(b.sort_comparator);
      });

      // Check if roms should be grouped
      if (!this._shouldGroupRoms()) {
        this._grouped = this.allRoms;
        return;
      }

      // Group roms by external id
      this._grouped = this._getGroupedRoms(this.allRoms).sort((a, b) => {
        return a.sort_comparator.localeCompare(b.sort_comparator);
      });
    },
    setCurrentPlatform(platform: Platform | null) {
      this.currentPlatform = platform;
    },
    setCurrentRom(rom: DetailedRom) {
      this.currentRom = rom;
    },
    setRecentRoms(roms: SimpleRom[]) {
      if (this._shouldGroupRoms()) {
        // Group by external ID to only display a single entry per sibling,
        // and sorted on rom ID in descending order.
        this.recentRoms = this._getGroupedRoms(roms).sort(
          (a, b) => b.id - a.id,
        );
      } else {
        this.recentRoms = roms;
      }
    },
    setContinuePlayedRoms(roms: SimpleRom[]) {
      this.continuePlayingRoms = roms;
    },
    setCurrentCollection(collection: Collection | null) {
      this.currentCollection = collection;
    },
    setCurrentVirtualCollection(collection: VirtualCollection | null) {
      this.currentVirtualCollection = collection;
    },
    fetchRoms(galleryFilter: GalleryFilterStore) {
      if (this.fetchingRoms) return Promise.resolve();
      this.fetchingRoms = true;

      return new Promise((resolve, reject) => {
        romApi
          .getRoms({
            ...galleryFilter.$state,
            platformId:
              this.currentPlatform?.id ??
              galleryFilter.selectedPlatform?.id ??
              null,
            collectionId: this.currentCollection?.id ?? null,
            virtualCollectionId: this.currentVirtualCollection?.id ?? null,
            limit: this.fetchLimit,
            offset: this.fetchOffset,
          })
          .then(({ data: { items, offset, total } }) => {
            if (offset !== null) this.fetchOffset = offset + this.fetchLimit;
            if (total !== null) this.fetchTotalRoms = total;

            // These need to happen in exactly this order
            this.allRoms = this.allRoms.concat(items);
            this._reorder();

            resolve(items);
          })
          .catch((error) => {
            reject(error);
          })
          .finally(() => {
            this.fetchingRoms = false;
          });
      });
    },
    refetchRoms(galleryFilter: GalleryFilterStore) {
      if (this.fetchingRoms) return Promise.resolve();
      this.fetchingRoms = true;
      this.resetPagination();

      return new Promise((resolve, reject) => {
        romApi
          .getRoms({
            ...galleryFilter.$state,
            platformId:
              this.currentPlatform?.id ??
              galleryFilter.selectedPlatform?.id ??
              null,
            collectionId: this.currentCollection?.id ?? null,
            virtualCollectionId: this.currentVirtualCollection?.id ?? null,
            limit: this.fetchLimit,
            offset: this.fetchOffset,
          })
          .then(({ data: { items, offset, total } }) => {
            if (offset !== null) this.fetchOffset = offset + this.fetchLimit;
            if (total !== null) this.fetchTotalRoms = total;

            // These need to happen in exactly this order
            this.allRoms = items;
            this._reorder();

            resolve(items);
          })
          .catch((error) => {
            reject(error);
          })
          .finally(() => {
            this.fetchingRoms = false;
          });
      });
    },
    add(roms: SimpleRom[]) {
      this.allRoms = this.allRoms.concat(roms);
      this._reorder();
    },
    addToRecent(rom: SimpleRom) {
      this.recentRoms = [rom, ...this.recentRoms];
    },
    removeFromRecent(rom: SimpleRom) {
      this.recentRoms = this.recentRoms.filter((value) => value.id !== rom.id);
    },
    addToContinuePlaying(rom: SimpleRom) {
      this.continuePlayingRoms = [rom, ...this.continuePlayingRoms];
    },
    removeFromContinuePlaying(rom: SimpleRom) {
      this.continuePlayingRoms = this.continuePlayingRoms.filter(
        (value) => value.id !== rom.id,
      );
    },
    update(rom: SimpleRom) {
      this.allRoms = this.allRoms.map((value) =>
        value.id === rom.id ? rom : value,
      );
      this.recentRoms = this.recentRoms.map((value) =>
        value.id === rom.id ? rom : value,
      );
      this._reorder();
    },
    remove(roms: SimpleRom[]) {
      this.allRoms = this.allRoms.filter((value) => {
        return !roms.find((rom) => {
          return rom.id === value.id;
        });
      });
      this._grouped = this._grouped.filter((value) => {
        return !roms.find((rom) => {
          return rom.id === value.id;
        });
      });
    },
    reset() {
      Object.assign(this, {
        ...defaultRomsState,
        recentRoms: this.recentRoms,
        continuePlayingRoms: this.continuePlayingRoms,
      });
    },
    resetPagination() {
      this.fetchLimit = 72;
      this.fetchOffset = 0;
      this.fetchTotalRoms = 0;
    },
    setSelection(roms: SimpleRom[]) {
      this._selectedIDs = new Set(roms.map((rom) => rom.id));
    },
    addToSelection(rom: SimpleRom) {
      this._selectedIDs.add(rom.id);
    },
    removeFromSelection(rom: SimpleRom) {
      this._selectedIDs.delete(rom.id);
    },
    updateLastSelected(index: number) {
      this.lastSelectedIndex = index;
    },
    setSelecting() {
      this.selectingRoms = !this.selectingRoms;
    },
    resetSelection() {
      this._selectedIDs = new Set<number>();
      this.lastSelectedIndex = -1;
    },
    isSimpleRom(rom: SimpleRom | SearchRomSchema): rom is SimpleRom {
      return !isNull(rom.id) && !isUndefined(rom.id);
    },
  },
});
