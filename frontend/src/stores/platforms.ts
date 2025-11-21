import { uniqBy } from "lodash";
import { defineStore } from "pinia";
import type { PlatformSchema } from "@/__generated__";
import platformApi from "@/services/api/platform";

export type Platform = PlatformSchema;

export default defineStore("platforms", {
  state: () => ({
    allPlatforms: [] as Platform[],
    filterText: "" as string,
    fetchingPlatforms: false as boolean,
  }),

  getters: {
    totalGames: ({ allPlatforms: value }) =>
      value.reduce((count, p) => count + p.rom_count, 0),
    filledPlatforms: ({ allPlatforms: all }) =>
      all
        .filter((p) => p.rom_count > 0)
        .sort((a, b) => a.display_name.localeCompare(b.display_name)),
    filteredPlatforms: ({ allPlatforms: all, filterText }) =>
      all
        .filter(
          (p) =>
            p.rom_count > 0 &&
            p.display_name.toLowerCase().includes(filterText.toLowerCase()),
        )
        .sort((a, b) => a.display_name.localeCompare(b.display_name)),
  },

  actions: {
    _reorder() {
      this.allPlatforms = uniqBy(this.allPlatforms, "id").sort((a, b) => {
        return a.name.localeCompare(b.name);
      });
    },
    fetchPlatforms(): Promise<Platform[]> {
      if (this.fetchingPlatforms) return Promise.resolve([]);
      this.fetchingPlatforms = true;

      return new Promise((resolve, reject) => {
        platformApi
          .getPlatforms()
          .then(({ data: platforms }) => {
            this.allPlatforms = platforms;
            resolve(platforms);
          })
          .catch((error) => {
            console.error(error);
            reject(error);
          })
          .finally(() => {
            this.fetchingPlatforms = false;
          });
      });
    },
    set(platforms: Platform[]) {
      this.allPlatforms = platforms;
    },
    add(platform: Platform) {
      this.allPlatforms.push(platform);
      this._reorder();
    },
    update(platform: Platform) {
      const index = this.allPlatforms.findIndex((p) => p.id === platform.id);
      this.allPlatforms[index] = platform;
      this._reorder();
    },
    has(id: number) {
      return this.allPlatforms.some((p) => p.id == id);
    },
    remove(platform: Platform) {
      this.allPlatforms = this.allPlatforms.filter((p) => {
        return p.slug !== platform.slug;
      });
    },
    get(platformId: number) {
      return this.allPlatforms.find((p) => p.id === platformId);
    },
    reset() {
      this.allPlatforms = [] as Platform[];
      this.filterText = "";
    },
  },
});
