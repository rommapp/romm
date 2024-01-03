import { uniqBy, groupBy, isNull } from "lodash";
import { defineStore } from "pinia";
import { nanoid } from "nanoid";

export type Rom = {
  id: number;
  igdb_id: number | undefined;
  sgdb_id: number | undefined;
  platform_slug: string;
  platform_name: string;
  file_name: string;
  file_name_no_tags: string;
  file_extension: string;
  file_path: string;
  file_size: number;
  file_size_units: string;
  file_size_bytes: number;
  name: string | undefined;
  slug: string | undefined;
  summary: string | undefined;
  sort_comparator: string;
  path_cover_s: string;
  path_cover_l: string;
  has_cover: boolean;
  url_cover: string;
  revision: string | undefined;
  regions: string[];
  languages: string[];
  tags: string[];
  multi: boolean;
  files: string[];
  url_screenshots: string[];
  path_screenshots: string[];
  full_path: string;
  download_path: string;
  sibling_roms?: Rom[];
  siblings?: Rom[];
};

export default defineStore("roms", {
  state: () => ({
    _platform: "",
    recentRoms: [] as Rom[],
    _all: [] as Rom[],
    _grouped: [] as Rom[],
    _filteredIDs: [] as number[],
    _searchIDs: [] as number[],
    _selectedIDs: [] as number[],
    lastSelectedIndex: -1,
    cursor: "",
    searchCursor: "",
    touchScreen: false,
  }),

  getters: {
    platform: (state) => state._platform,
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

      // Group roms by igdb_id
      this._grouped = Object.values(
        groupBy(this._all, (game) =>
          // If igdb_id is null, generate a random id so that the roms are not grouped
          isNull(game.igdb_id) ? nanoid() : game.igdb_id
        )
      ).map((games) => ({
        ...games.shift() as Rom,
        siblings: games,
      }));
    },
    setPlatform(platform: string) {
      this._platform = platform;
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
    },
    reset() {
      this._all = [];
      this._grouped = [];
      this._filteredIDs = [];
      this._searchIDs = [];
      this._selectedIDs = [];
      this.lastSelectedIndex = -1;
    },

    // Filtered roms
    setFiltered(roms: Rom[]) {
      this._filteredIDs = roms.map((rom) => rom.id);
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
    isTouchScreen(touchScreen: boolean) {
      this.touchScreen = touchScreen;
    },
    resetSelection() {
      this._selectedIDs = [];
      this.lastSelectedIndex = -1;
    },
  },
});
