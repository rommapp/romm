import { defineStore } from "pinia";

export default defineStore("platforms", {
  state: () => {
    return {
      platforms: []
    };
  },
  getters: {
    totalGames: ({ platforms }) => {
      debugger;
      platforms?.reduce((count, p) => {
        return count + p.n_roms;
      }, 0) ?? 0;
    },
  },
  actions: {
    set(platforms) {
      this.platforms = platforms;
    },
  },
});
