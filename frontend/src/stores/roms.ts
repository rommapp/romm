import type { SearchRomSchema } from "@/__generated__";
import type { DetailedRomSchema, SimpleRomSchema } from "@/__generated__/";
import romApi from "@/services/api/rom";
import { type Collection, type VirtualCollection } from "@/stores/collections";
import storeGalleryFilter from "@/stores/galleryFilter";
import { type Platform } from "@/stores/platforms";
import type { ExtractPiniaStoreType } from "@/types";
import { isNull, isUndefined } from "lodash";
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
  selectedIDs: new Set<number>(),
  recentRoms: [] as SimpleRom[],
  continuePlayingRoms: [] as SimpleRom[],
  lastSelectedIndex: -1,
  selectingRoms: false,
  fetchingRoms: false,
  initialSearch: false,
  fetchLimit: 72,
  fetchOffset: 0,
  fetchTotalRoms: 0,
  characterIndex: {} as Record<string, number>,
  selectedCharacter: null as string | null,
  orderBy: "name" as keyof SimpleRom,
  orderDir: "asc" as "asc" | "desc",
};

// This caches the first 72 roms fetched for each platform
const _romsCacheByPlatform = new Map<number, SimpleRom[]>();
const _romsCacheByCollection = new Map<number, SimpleRom[]>();
const _romsCacheByVirtualCollection = new Map<string, SimpleRom[]>();

export default defineStore("roms", {
  state: () => ({ ...defaultRomsState }),

  getters: {
    filteredRoms: (state) => state.allRoms,
    selectedRoms: (state) =>
      state.allRoms.filter((rom) => state.selectedIDs.has(rom.id)),
  },

  actions: {
    _shouldGroupRoms(): boolean {
      return isNull(localStorage.getItem("settings.groupRoms"))
        ? true
        : localStorage.getItem("settings.groupRoms") === "true";
    },
    setCurrentPlatform(platform: Platform | null) {
      this.currentPlatform = platform;
      if (platform) {
        this.allRoms = _romsCacheByPlatform.get(platform.id) ?? [];
      }
    },
    setCurrentRom(rom: DetailedRom) {
      this.currentRom = rom;
    },
    setRecentRoms(roms: SimpleRom[]) {
      this.recentRoms = roms;
    },
    setContinuePlayedRoms(roms: SimpleRom[]) {
      this.continuePlayingRoms = roms;
    },
    setCurrentCollection(collection: Collection | null) {
      this.currentCollection = collection;
      if (collection) {
        this.allRoms = _romsCacheByCollection.get(collection.id) ?? [];
      }
    },
    setCurrentVirtualCollection(collection: VirtualCollection | null) {
      this.currentVirtualCollection = collection;
      if (collection) {
        this.allRoms = _romsCacheByVirtualCollection.get(collection.id) ?? [];
      }
    },
    fetchRoms(galleryFilter: GalleryFilterStore, concat = true) {
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
            orderBy: this.orderBy,
            orderDir: this.orderDir,
            groupByMetaId: this._shouldGroupRoms(),
          })
          .then(({ data: { items, offset, total, char_index } }) => {
            if (!concat || this.fetchOffset === 0) {
              this.allRoms = items;

              // Cache the first batch of roms for each platform
              if (this.currentPlatform) {
                _romsCacheByPlatform.set(this.currentPlatform.id, items);
              } else if (this.currentCollection) {
                _romsCacheByCollection.set(this.currentCollection.id, items);
              } else if (this.currentVirtualCollection) {
                _romsCacheByVirtualCollection.set(
                  this.currentVirtualCollection.id,
                  items,
                );
              }
            } else {
              this.allRoms = this.allRoms.concat(items);
            }

            // Update the offset and total roms in filtered database result
            if (offset !== null) this.fetchOffset = offset + this.fetchLimit;
            if (total !== null) this.fetchTotalRoms = total;

            // Set the character index for the current platform
            this.characterIndex = char_index;

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
    },
    remove(roms: SimpleRom[]) {
      this.allRoms = this.allRoms.filter((value) => {
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
    },
    setOrderDir(orderDir: "asc" | "desc") {
      this.orderDir = orderDir;
    },
    isSimpleRom(rom: SimpleRom | SearchRomSchema): rom is SimpleRom {
      return !isNull(rom.id) && !isUndefined(rom.id);
    },
  },
});
