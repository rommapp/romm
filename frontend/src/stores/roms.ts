import type { SearchRomSchema } from "@/__generated__";
import type { DetailedRomSchema, RomSchema } from "@/__generated__/";
import { type Platform } from "@/stores/platforms";
import { type Collection } from "@/stores/collections";
import type { ExtractPiniaStoreType } from "@/types";
import { groupBy, uniqBy } from "lodash";
import { nanoid } from "nanoid";
import { defineStore } from "pinia";
import storeGalleryFilter from "./galleryFilter";
import storeCollection from "./collections";

type GalleryFilterStore = ExtractPiniaStoreType<typeof storeGalleryFilter>;

const collectionStore = storeCollection();

export type SimpleRom = RomSchema & {
  siblings?: RomSchema[]; // Added by the frontend
};

export type DetailedRom = DetailedRomSchema;

export default defineStore("roms", {
  state: () => ({
    currentPlatform: null as Platform | null,
    currentCollection: null as Collection | null,
    currentRom: null as DetailedRom | null,
    allRoms: [] as SimpleRom[],
    _grouped: [] as SimpleRom[],
    _filteredIDs: [] as number[],
    _selectedIDs: [] as number[],
    recentRoms: [] as SimpleRom[],
    lastSelectedIndex: -1,
    selecting: false,
    itemsPerBatch: 72,
    gettingRoms: false,
  }),

  getters: {
    filteredRoms: (state) =>
      state._grouped.filter((rom) => state._filteredIDs.includes(rom.id)),
    selectedRoms: (state) =>
      state._grouped.filter((rom) => state._selectedIDs.includes(rom.id)),
  },

  actions: {
    _reorder() {
      // Sort roms by comparator string
      this.allRoms = this.allRoms.sort((a, b) => {
        return a.sort_comparator.localeCompare(b.sort_comparator);
      });
      this.allRoms = uniqBy(this.allRoms, "id");

      // Check if roms should be grouped
      const groupRoms = localStorage.getItem("settings.groupRoms") === "true";
      if (!groupRoms) {
        this._grouped = this.allRoms;
        return;
      }

      // Group roms by external id
      this._grouped = Object.values(
        groupBy(
          this.allRoms,
          (game) =>
            // If external id is null, generate a random id so that the roms are not grouped
            game.igdb_id || game.moby_id || nanoid(),
        ),
      )
        .map((games) => {
          // Find the index of the game where the 'rom_user' property has 'is_main_sibling' set to true.
          // If such a game is found, 'mainSiblingIndex' will be its index, otherwise it will be -1.
          const mainSiblingIndex = games.findIndex(
            (game) => game.rom_user?.is_main_sibling,
          );

          // Determine the primary game:
          // - If 'mainSiblingIndex' is not -1 (i.e., a main sibling game was found),
          //   remove that game from the 'games' array and set it as 'primaryGame'.
          // - If no main sibling game was found ('mainSiblingIndex' is -1),
          //   remove the first game from the 'games' array and set it as 'primaryGame'.
          const primaryGame =
            mainSiblingIndex !== -1
              ? games.splice(mainSiblingIndex, 1)[0]
              : games.shift();

          return {
            ...(primaryGame as SimpleRom),
            siblings: games,
          };
        })
        .sort((a, b) => {
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
      this.recentRoms = roms;
    },
    setCurrentCollection(collection: Collection | null) {
      this.currentCollection = collection;
    },
    set(roms: SimpleRom[]) {
      this.allRoms = roms;
      this._reorder();
    },
    add(roms: SimpleRom[]) {
      this.allRoms = this.allRoms.concat(roms);
      this._reorder();
    },
    addToRecent(rom: SimpleRom) {
      this.recentRoms = [rom, ...this.recentRoms];
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
      this._filteredIDs = this._filteredIDs.filter((value) => {
        return !roms.find((rom) => {
          return rom.id === value;
        });
      });
    },
    reset() {
      this.allRoms = [];
      this._grouped = [];
      this._filteredIDs = [];
      this._selectedIDs = [];
      this.lastSelectedIndex = -1;
    },
    // Filter roms by gallery filter store state
    setFiltered(roms: SimpleRom[], galleryFilter: GalleryFilterStore) {
      this._filteredIDs = roms.map((rom) => rom.id);
      if (galleryFilter.filterSearch) {
        this._filterSearch(galleryFilter.filterSearch);
      }
      if (galleryFilter.filterUnmatched) {
        this._filterUnmatched();
      }
      if (galleryFilter.filterFavourites) {
        this._filterFavourites();
      }
      if (galleryFilter.selectedGenre) {
        this._filterGenre(galleryFilter.selectedGenre);
      }
      if (galleryFilter.selectedFranchise) {
        this._filterFranchise(galleryFilter.selectedFranchise);
      }
      if (galleryFilter.selectedCollection) {
        this._filterCollection(galleryFilter.selectedCollection);
      }
      if (galleryFilter.selectedCompany) {
        this._filterCompany(galleryFilter.selectedCompany);
      }
    },
    _filterSearch(searchFilter: string) {
      this._filteredIDs = this.filteredRoms
        .filter(
          (rom) =>
            rom.name?.toLowerCase().includes(searchFilter.toLowerCase()) ||
            rom.file_name?.toLowerCase().includes(searchFilter.toLowerCase()),
        )
        .map((roms) => roms.id);
    },
    _filterUnmatched() {
      this._filteredIDs = this.filteredRoms
        .filter((rom) => !rom.igdb_id && !rom.moby_id)
        .map((roms) => roms.id);
    },
    _filterFavourites() {
      this._filteredIDs = this.filteredRoms
        .filter((rom) => collectionStore.favCollection?.roms?.includes(rom.id))
        .map((roms) => roms.id);
    },
    _filterGenre(genreToFilter: string) {
      this._filteredIDs = this.filteredRoms
        .filter((rom) => rom.genres.some((genre) => genre === genreToFilter))
        .map((rom) => rom.id);
    },
    _filterFranchise(franchiseToFilter: string) {
      this._filteredIDs = this.filteredRoms
        .filter((rom) =>
          rom.franchises.some((franchise) => franchise === franchiseToFilter),
        )
        .map((rom) => rom.id);
    },
    _filterCollection(collectionToFilter: string) {
      this._filteredIDs = this.filteredRoms
        .filter((rom) =>
          rom.collections.some(
            (collection) => collection === collectionToFilter,
          ),
        )
        .map((rom) => rom.id);
    },
    _filterCompany(companyToFilter: string) {
      this._filteredIDs = this.filteredRoms
        .filter((rom) =>
          rom.companies.some((company) => company === companyToFilter),
        )
        .map((rom) => rom.id);
    },
    // Selected roms
    setSelection(roms: SimpleRom[]) {
      this._selectedIDs = roms.map((rom) => rom.id);
    },
    addToSelection(rom: SimpleRom) {
      this._selectedIDs.push(rom.id);
    },
    removeFromSelection(rom: SimpleRom) {
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
    isSimpleRom(rom: SimpleRom | SearchRomSchema): rom is SimpleRom {
      return (rom as SimpleRom).id !== undefined;
    },
  },
});
