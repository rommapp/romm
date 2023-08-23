import { defineStore } from "pinia";

export default defineStore("roms", {
  state: () => ({ selected: [], lastSelected: -1 }),

  actions: {
    updateSelectedRoms(roms) {
      this.selected = roms;
    },
    addSelectedRoms(rom) {
      this.selected.push(rom);
    },
    removeSelectedRoms(rom) {
      this.selected = this.selected.filter(function (value) {
        return value.id != rom.id;
      });
    },
    updateLastSelectedRom(rom) {
      this.lastSelected = rom;
    },
    reset(){
      this.selected = [];
      this.lastSelected = -1;
    }
  },
});
