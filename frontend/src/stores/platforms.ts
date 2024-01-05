import { defineStore } from "pinia";
import type { PlatformSchema } from "@/__generated__";

export type Platform = PlatformSchema;

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
    remove(platform: Platform) {
      this.value = this.value.filter((p) => {
        return p.slug !== platform.slug;
      });
    },
  },
});
