import { defineStore } from "pinia";

export type Platform = {
  slug: string;
  fs_slug: string;
  igdb_id: number | undefined;
  sgdb_id: number | undefined;
  name: string | undefined;
  logo_path: string;
  rom_count: number;
};

export default defineStore("platforms", {
  state: () => {
    return {
      value: [] as Platform[],
    };
  },
  getters: {
    totalGames: ({ value }) =>
      value.reduce((count, p) => count + p.rom_count, 0),
    filledPlatforms: ({ value }) => value.filter((p) => p.rom_count > 0),
  },
  actions: {
    set(platforms: Platform[]) {
      this.value = platforms;
    },
  },
});
