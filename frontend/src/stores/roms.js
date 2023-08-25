import { defineStore } from "pinia";

export default defineStore("roms", {
  state: () => ({ selected: [], lastSelectedIndex: -1 }),

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
    updateLastSelectedRom(index) {
      this.lastSelectedIndex = index;
    },
    reset(){
      this.selected = [];
      this.lastSelectedIndex = -1;
    }
  },
});
