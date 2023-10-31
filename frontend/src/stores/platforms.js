import { defineStore } from "pinia";

export default defineStore("platforms", {
  state: () => {
    return {
      value: [],
    };
  },
  getters: {
    totalGames: ({ value }) => value.reduce((count, p) => count + p.n_roms, 0),
    filledPlatforms: ({ value }) => value.filter((p) => p.n_roms > 0),
  },
  actions: {
    set(platforms) {
      this.value = platforms;
    },
  },
});
