import type { PlatformSchema, RomSchema } from "@/__generated__/";
import { groupBy, isNull, uniqBy } from "lodash";
import { nanoid } from "nanoid";
import { defineStore, type Store } from "pinia";
import storeGalleryFilter from "./galleryFilter";
import type { ExtractPiniaStoreType } from "@/types";

type GalleryFilterStore = ExtractPiniaStoreType<typeof storeGalleryFilter>;

export type Rom = RomSchema & {
  siblings?: RomSchema[]; // Added by the frontend
};

export default defineStore("roms", {
  state: () => ({
    _platformID: 0,
    _all: [] as Rom[],
    _grouped: [] as Rom[],
    _filteredIDs: [] as number[],
    _searchIDs: [] as number[],
    _selectedIDs: [] as number[],
    recentRoms: [] as Rom[],
    lastSelectedIndex: -1,
    cursor: "" as string | null,
    searchCursor: "" as string | null,
    selecting: false,
  }),

  getters: {
    platformID: (state) => state._platformID,
    allRoms: (state) => state._all,
    filteredRoms: (state) =>
      state._grouped.filter((rom) => state._filteredIDs.includes(rom.id)),
    searchRoms: (state) =>
      state._grouped.filter((rom) => state._searchIDs.includes(rom.id)),
    selectedRoms: (state) =>
      state._grouped.filter((rom) => state._selectedIDs.includes(rom.id)),
  },

  actions: {
    _reorder() {
      // Sort roms by comparator string
      this._all = this._all.sort((a, b) => {
        return a.sort_comparator.localeCompare(b.sort_comparator);
      });
      this._all = uniqBy(this._all, "id");

      // Check if roms should be grouped
      const groupRoms = localStorage.getItem("settings.groupRoms") === "true";
      if (!groupRoms) {
        this._grouped = this._all;
        return;
      }

      // Group roms by external id
      this._grouped = Object.values(
        groupBy(
          this._all,
          (game) =>
            // If external id is null, generate a random id so that the roms are not grouped
            game.igdb_id || game.moby_id || nanoid()
        )
      )
        .map((games) => ({
          ...(games.shift() as Rom),
          siblings: games,
        }))
        .sort((a, b) => {
          return a.sort_comparator.localeCompare(b.sort_comparator);
        });
    },
    setPlatformID(platformID: number) {
      this._platformID = platformID;
    },
    setRecentRoms(roms: Rom[]) {
      this.recentRoms = roms;
    },
    // All roms
    set(roms: Rom[]) {
      this._all = roms;
      this._reorder();
    },
    add(roms: Rom[]) {
      this._all = this._all.concat(roms);
      this._reorder();
    },
    update(rom: Rom) {
      this._all = this._all.map((value) => (value.id === rom.id ? rom : value));
      this._reorder();
    },
    remove(roms: Rom[]) {
      this._all = this._all.filter((value) => {
        return !roms.find((rom) => {
          return rom.id === value.id;
        });
      });
      this._grouped = this._grouped.filter((value) => {
        return !roms.find((rom) => {
          return rom.id === value.id;
        });
      });
      this._filteredIDs = this._filteredIDs.filter((value) => {
        return !roms.find((rom) => {
          return rom.id === value;
        });
      });
    },
    reset() {
      this._all = [];
      this._grouped = [];
      this._filteredIDs = [];
      this._searchIDs = [];
      this._selectedIDs = [];
      this.lastSelectedIndex = -1;
    },
    // Filter roms by gallery filter store state
    setFiltered(roms: Rom[], galleryFilter: GalleryFilterStore) {
      this._filteredIDs = roms.map((rom) => rom.id);
      if (galleryFilter.filterUnmatched) this.filterUnmatched();
      if (galleryFilter.selectedGenre) {
        this.filterGenre(galleryFilter.selectedGenre);
      }
      if (galleryFilter.selectedFranchise) {
        this.filterFranchise(galleryFilter.selectedFranchise);
      }
      if (galleryFilter.selectedCollection) {
        this.filterCollection(galleryFilter.selectedCollection);
      }
      if (galleryFilter.selectedCompany) {
        this.filterCompany(galleryFilter.selectedCompany);
      }
    },
    filterUnmatched() {
      this._filteredIDs = this.filteredRoms
        .filter((rom) => !rom.igdb_id && !rom.moby_id)
        .map((roms) => roms.id);
    },
    filterGenre(genreToFilter: string) {
      this._filteredIDs = this.filteredRoms
        .filter((rom) => rom.genres.some((genre) => genre === genreToFilter))
        .map((rom) => rom.id);
    },
    filterFranchise(franchiseToFilter: string) {
      this._filteredIDs = this.filteredRoms
        .filter((rom) =>
          rom.franchises.some((franchise) => franchise === franchiseToFilter)
        )
        .map((rom) => rom.id);
    },
    filterCollection(collectionToFilter: string) {
      this._filteredIDs = this.filteredRoms
        .filter((rom) =>
          rom.collections.some(
            (collection) => collection === collectionToFilter
          )
        )
        .map((rom) => rom.id);
    },
    filterCompany(companyToFilter: string) {
      this._filteredIDs = this.filteredRoms
        .filter((rom) =>
          rom.companies.some((company) => company === companyToFilter)
        )
        .map((rom) => rom.id);
    },
    // Search roms
    setSearch(roms: Rom[]) {
      this._searchIDs = roms.map((rom) => rom.id);
    },
    // Selected roms
    setSelection(roms: Rom[]) {
      this._selectedIDs = roms.map((rom) => rom.id);
    },
    addToSelection(rom: Rom) {
      this._selectedIDs.push(rom.id);
    },
    removeFromSelection(rom: Rom) {
      this._selectedIDs = this._selectedIDs.filter((id) => {
        return id !== rom.id;
      });
    },
    updateLastSelected(index: number) {
      this.lastSelectedIndex = index;
    },
    isSelecting() {
      this.selecting = !this.selecting;
    },
    resetSelection() {
      this._selectedIDs = [];
      this.lastSelectedIndex = -1;
    },
  },
});
