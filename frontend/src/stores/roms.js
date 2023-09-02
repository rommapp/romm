import { defineStore } from "pinia";

export default defineStore("roms", {
  state: () => ({
    _all: [],
    _filteredIDs: [],
    _searchIDs: [],
    _selectedIDs: [],
    lastSelectedIndex: -1,
  }),

  getters: {
    all: (state) => state._all,
    filtered: (state) => state._all.filter((rom) => state._filteredIDs.includes(rom.id)),
    search: (state) => state._all.filter((rom) => state._searchIDs.includes(rom.id)),
    selected: (state) =>  state._all.filter((rom) => state._selectedIDs.includes(rom.id)),
  },

  actions: {
    // All roms
    set(roms) {
      this._all = roms;
    },
    add(roms) {
      this._all = this._all.concat(roms);
    },
    update(rom) {
      this._all = this._all.map((value) => {
        if (value.id === rom.id) {
          return rom;
        }
        return value;
      });
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
      this._selectedIDs =  roms.map((rom) => rom.id);
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
    resetSelection() {
      this._selectedIDs = [];
      this.lastSelectedIndex = -1;
    },
  },
});
