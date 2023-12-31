import { uniqBy } from "lodash";
import { defineStore } from "pinia";

export default defineStore("roms", {
  state: () => ({
    _platform: "",
    recentRoms: [],
    _all: [],
    _filteredIDs: [],
    _searchIDs: [],
    _selectedIDs: [],
    lastSelectedIndex: -1,
    cursor: "",
    searchCursor: "",
    touchScreen: false,
  }),

  getters: {
    platform: (state) => state._platform,
    allRoms: (state) => state._all,
    filteredRoms: (state) =>
      state._all.filter((rom) => state._filteredIDs.includes(rom.id)),
    searchRoms: (state) =>
      state._all.filter((rom) => state._searchIDs.includes(rom.id)),
    selectedRoms: (state) =>
      state._all.filter((rom) => state._selectedIDs.includes(rom.id)),
  },

  actions: {
    _reorder() {
      // Sort roms by comparator string
      this._all = uniqBy(
        this._all.sort((a, b) => {
          return a.sort_comparator.localeCompare(b.sort_comparator);
        }),
        "id"
      );
    },
    setPlatform(platform) {
      this._platform = platform;
    },
    setRecentRoms(roms) {
      this.recentRoms = roms;
    },
    // All roms
    set(roms) {
      this._all = roms;
      this._reorder();
    },
    add(roms) {
      this._all = this._all.concat(roms);
      this._reorder();
    },
    update(rom) {
      this._all = this._all.map((value) => (value.id === rom.id ? rom : value));
      this._reorder();
    },
    remove(roms) {
      this._all = this._all.filter((value) => {
        return !roms.find((rom) => {
          return rom.id === value.id;
        });
      });
    },
    reset() {
      this._all = [];
      this._filteredIDs = [];
      this._searchIDs = [];
      this._selectedIDs = [];
      this.lastSelectedIndex = -1;
    },

    // Filtered roms
    setFiltered(roms) {
      this._filteredIDs = roms.map((rom) => rom.id);
    },

    // Search roms
    setSearch(roms) {
      this._searchIDs = roms.map((rom) => rom.id);
    },

    // Selected roms
    setSelection(roms) {
      this._selectedIDs = roms.map((rom) => rom.id);
    },
    addToSelection(rom) {
      this._selectedIDs.push(rom.id);
    },
    removeFromSelection(rom) {
      this._selectedIDs = this._selectedIDs.filter((id) => {
        return id !== rom.id;
      });
    },
    updateLastSelected(index) {
      this.lastSelectedIndex = index;
    },
    isTouchScreen(touchScreen) {
      this.touchScreen = touchScreen;
    },
    resetSelection() {
      this._selectedIDs = [];
      this.lastSelectedIndex = -1;
    },
  },
});
