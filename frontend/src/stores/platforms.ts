import { defineStore } from "pinia";
import type { PlatformSchema } from "@/__generated__";
import { uniqBy } from "lodash";

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
    _reorder() {
      this.value = this.value.sort((a, b) => {
        return a.name.localeCompare(b.name);
      });
      this.value = uniqBy(this.value, "id");
    },
    set(platforms: Platform[]) {
      this.value = platforms;
    },
    add(platform: Platform) {
      this.value.push(platform)
      this._reorder()
    },
    exists(platform: Platform) {
      return this.value.filter(p => p.fs_slug == platform.fs_slug).length > 0
    },
    remove(platform: Platform) {
      this.value = this.value.filter((p) => {
        return p.slug !== platform.slug;
      });
    },
    get(platformId: number){
      return this.value.find((p) => p.id === platformId);
    }
  },
});
