import { defineStore } from "pinia";

export default defineStore("platforms", {
  state: () => ({ value: [] }),

  actions: {
    set(platforms) {
      this.value = platforms;
    },
    getTotalGames() {
      return this.value.reduce((count, p) => {
        return count + p.n_roms;
      }, 0);
    },
  },
});
