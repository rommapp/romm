import type { SearchRomSchema } from "@/__generated__";
import type { DetailedRomSchema, SimpleRomSchema } from "@/__generated__/";
import storeCollection, { type Collection } from "@/stores/collections";
import storeGalleryFilter from "@/stores/galleryFilter";
import { type Platform } from "@/stores/platforms";
import type { ExtractPiniaStoreType } from "@/types";
import { getStatusKeyForText } from "@/utils";
import { groupBy, isNull, uniqBy } from "lodash";
import { nanoid } from "nanoid";
import { defineStore } from "pinia";

type GalleryFilterStore = ExtractPiniaStoreType<typeof storeGalleryFilter>;

const collectionStore = storeCollection();

export type SimpleRom = SimpleRomSchema;
export type DetailedRom = DetailedRomSchema;

export default defineStore("roms", {
  state: () => ({
    currentPlatform: null as Platform | null,
    currentCollection: null as Collection | null,
    currentRom: null as DetailedRom | null,
    allRoms: [] as SimpleRom[],
    _grouped: [] as SimpleRom[],
    _filteredIDs: new Set<number>(),
    _selectedIDs: new Set<number>(),
    recentRoms: [] as SimpleRom[],
    continuePlayingRoms: [] as SimpleRom[],
    lastSelectedIndex: -1,
    selecting: false,
    itemsPerBatch: 72,
    gettingRoms: false,
  }),

  getters: {
    filteredRoms: (state) =>
      state._grouped.filter((rom) => state._filteredIDs.has(rom.id)),
    selectedRoms: (state) =>
      state._grouped.filter((rom) => state._selectedIDs.has(rom.id)),
  },

  actions: {
    _reorder() {
      // Sort roms by comparator string
      this.allRoms = uniqBy(this.allRoms, "id").sort((a, b) => {
        return a.sort_comparator.localeCompare(b.sort_comparator);
      });

      // Check if roms should be grouped
      const groupRoms = isNull(localStorage.getItem("settings.groupRoms"))
        ? true
        : localStorage.getItem("settings.groupRoms") === "true";
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
          return (
            games.find((game) => game.rom_user?.is_main_sibling) || games[0]
          );
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
    setContinuePlayedRoms(roms: SimpleRom[]) {
      this.continuePlayingRoms = roms;
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
    addToContinuePlaying(rom: SimpleRom) {
      this.continuePlayingRoms = [rom, ...this.continuePlayingRoms];
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
      roms.forEach((rom) => this._filteredIDs.delete(rom.id));
    },
    reset() {
      this.allRoms = [];
      this._grouped = [];
      this._filteredIDs = new Set<number>();
      this._selectedIDs = new Set<number>();
      this.lastSelectedIndex = -1;
    },
    // Filter roms by gallery filter store state
    setFiltered(roms: SimpleRom[], galleryFilter: GalleryFilterStore) {
      this._filteredIDs = new Set(roms.map((rom) => rom.id));
      if (galleryFilter.filterText) {
        this._filterText(galleryFilter.filterText);
      }
      if (galleryFilter.filterUnmatched) {
        this._filterUnmatched();
      }
      if (galleryFilter.filterMatched) {
        this._filterMatched();
      }
      if (galleryFilter.filterFavourites) {
        this._filterFavourites();
      }
      if (galleryFilter.filterDuplicates) {
        this._filterDuplicates();
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
      if (galleryFilter.selectedAgeRating) {
        this._filterAgeRating(galleryFilter.selectedAgeRating);
      }
      if (galleryFilter.selectedStatus) {
        this._filterStatus(galleryFilter.selectedStatus);
      } else {
        this._filteredIDs = new Set(
          // Filter hidden roms if the status is not hidden
          this.filteredRoms
            .filter((rom) => !rom.rom_user.hidden)
            .map((rom) => rom.id),
        );
      }
    },
    _filterText(searchFilter: string) {
      const bySearch = new Set(
        this.filteredRoms
          .filter(
            (rom) =>
              rom.name?.toLowerCase().includes(searchFilter.toLowerCase()) ||
              rom.file_name?.toLowerCase().includes(searchFilter.toLowerCase()),
          )
          .map((roms) => roms.id),
      );

      // @ts-expect-error intersection is recently defined on Set
      this._filteredIDs = bySearch.intersection(this._filteredIDs);
    },
    _filterUnmatched() {
      const byUnmatched = new Set(
        this.filteredRoms
          .filter((rom) => !rom.igdb_id && !rom.moby_id)
          .map((roms) => roms.id),
      );

      // @ts-expect-error intersection is recently defined on Set
      this._filteredIDs = byUnmatched.intersection(this._filteredIDs);
    },
    _filterMatched() {
      const byMatched = new Set(
        this.filteredRoms
          .filter((rom) => rom.igdb_id || rom.moby_id)
          .map((roms) => roms.id),
      );

      // @ts-expect-error intersection is recently defined on Set
      this._filteredIDs = byMatched.intersection(this._filteredIDs);
    },
    _filterFavourites() {
      const byFavourites = new Set(
        this.filteredRoms
          .filter((rom) =>
            collectionStore.favCollection?.roms?.includes(rom.id),
          )
          .map((roms) => roms.id),
      );

      // @ts-expect-error intersection is recently defined on Set
      this._filteredIDs = byFavourites.intersection(this._filteredIDs);
    },
    _filterDuplicates() {
      const byDuplicates = new Set(
        this.filteredRoms
          .filter((rom) => rom.sibling_roms?.length)
          .map((rom) => rom.id),
      );

      // @ts-expect-error intersection is recently defined on Set
      this._filteredIDs = byDuplicates.intersection(this._filteredIDs);
    },
    _filterGenre(genreToFilter: string) {
      const byGenre = new Set(
        this.filteredRoms
          .filter((rom) => rom.genres.some((genre) => genre === genreToFilter))
          .map((rom) => rom.id),
      );

      // @ts-expect-error intersection is recently defined on Set
      this._filteredIDs = byGenre.intersection(this._filteredIDs);
    },
    _filterFranchise(franchiseToFilter: string) {
      const byFranchise = new Set(
        this.filteredRoms
          .filter((rom) =>
            rom.franchises.some((franchise) => franchise === franchiseToFilter),
          )
          .map((rom) => rom.id),
      );

      // @ts-expect-error intersection is recently defined on Set
      this._filteredIDs = byFranchise.intersection(this._filteredIDs);
    },
    _filterCollection(collectionToFilter: string) {
      const byCollection = new Set(
        this.filteredRoms
          .filter((rom) =>
            rom.collections.some(
              (collection) => collection === collectionToFilter,
            ),
          )
          .map((rom) => rom.id),
      );

      // @ts-expect-error intersection is recently defined on Set
      this._filteredIDs = byCollection.intersection(this._filteredIDs);
    },
    _filterCompany(companyToFilter: string) {
      const byCompany = new Set(
        this.filteredRoms
          .filter((rom) =>
            rom.companies.some((company) => company === companyToFilter),
          )
          .map((rom) => rom.id),
      );

      // @ts-expect-error intersection is recently defined on Set
      this._filteredIDs = byCompany.intersection(this._filteredIDs);
    },
    _filterAgeRating(ageRatingToFilter: string) {
      const byAgeRating = new Set(
        this.filteredRoms
          .filter((rom) =>
            rom.age_ratings.some(
              (ageRating) => ageRating === ageRatingToFilter,
            ),
          )
          .map((rom) => rom.id),
      );

      // @ts-expect-error intersection is recently defined on Set
      this._filteredIDs = byAgeRating.intersection(this._filteredIDs);
    },
    _filterStatus(statusToFilter: string) {
      const stf = getStatusKeyForText(statusToFilter);

      const byStatus = new Set(
        this.filteredRoms
          .filter(
            (rom) =>
              rom.rom_user.status === stf ||
              (stf === "now_playing" && rom.rom_user.now_playing) ||
              (stf === "backlogged" && rom.rom_user.backlogged) ||
              (stf === "hidden" && rom.rom_user.hidden),
          )
          // Filter hidden roms if the status is not hidden
          .filter((rom) => (stf === "hidden" ? true : !rom.rom_user.hidden))
          .map((rom) => rom.id),
      );

      // @ts-expect-error intersection is recently defined on Set
      this._filteredIDs = byStatus.intersection(this._filteredIDs);
    },
    // Selected roms
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
    isSelecting() {
      this.selecting = !this.selecting;
    },
    resetSelection() {
      this._selectedIDs = new Set<number>();
      this.lastSelectedIndex = -1;
    },
    isSimpleRom(rom: SimpleRom | SearchRomSchema): rom is SimpleRom {
      return (rom as SimpleRom).id !== undefined;
    },
  },
});
