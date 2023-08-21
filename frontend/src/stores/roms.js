import { defineStore } from "pinia";

export default defineStore("roms", {
  state: () => ({ selected: [] }),

  actions: {
    updateSelectedRoms(roms) {
      this.selected = roms;
    },
    addSelectedRoms(rom) {
      this.selected.push(rom);
    },
    removeSelectedRoms(rom) {
      this.selected = this.selected.filter(function (value) {
        return value != rom;
      });
    },
  },
});
