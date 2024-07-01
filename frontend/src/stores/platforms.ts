import { defineStore } from "pinia";
import type { PlatformSchema } from "@/__generated__";
import { uniqBy } from "lodash";

export type Platform = PlatformSchema;

export default defineStore("platforms", {
  state: () => {
    return {
      all: [] as Platform[],
      searchText: "" as string,
    };
  },
  getters: {
    totalGames: ({ all: value }) =>
      value.reduce((count, p) => count + p.rom_count, 0),
    filledPlatforms: ({ all }) => all.filter((p) => p.rom_count > 0),
    filteredPlatforms: ({ all, searchText }) =>
      all.filter(
        (p) =>
          p.rom_count > 0 &&
          p.name.toLowerCase().includes(searchText.toLowerCase()),
      ),
  },
  actions: {
    _reorder() {
      this.all = this.all.sort((a, b) => {
        return a.name.localeCompare(b.name);
      });
      this.all = uniqBy(this.all, "id");
    },
    set(platforms: Platform[]) {
      this.all = platforms;
    },
    add(platform: Platform) {
      this.all.push(platform);
      this._reorder();
    },
    exists(platform: Platform) {
      return this.all.filter((p) => p.fs_slug == platform.fs_slug).length > 0;
    },
    remove(platform: Platform) {
      this.all = this.all.filter((p) => {
        return p.slug !== platform.slug;
      });
    },
    get(platformId: number) {
      return this.all.find((p) => p.id === platformId);
    },
  },
});
