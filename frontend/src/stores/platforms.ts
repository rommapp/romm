import { uniqBy } from "lodash";
import { defineStore } from "pinia";
import type { PlatformSchema } from "@/__generated__";
import platformApi from "@/services/api/platform";

export type Platform = PlatformSchema;

export default defineStore("platforms", {
  state: () => ({
    allPlatforms: [] as Platform[],
    // Folders on disk that have no database row yet (never-scanned
    // platforms). Fetched on demand by the scan view so a first scan can
    // target them. They carry id -1 and rom_count 0.
    filesystemPlatforms: [] as Platform[],
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
    // Everything a scan can target: existing database platforms (including
    // those with zero ROMs) plus unscanned folders on disk. Keyed by fs_slug
    // downstream, so the two sets never overlap (a folder with a database row
    // is excluded from filesystemPlatforms server-side).
    scannablePlatforms: ({ allPlatforms: all, filesystemPlatforms: fs }) =>
      [...all, ...fs].sort((a, b) =>
        a.display_name.localeCompare(b.display_name),
      ),
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
    fetchFilesystemPlatforms(): Promise<Platform[]> {
      return new Promise((resolve, reject) => {
        platformApi
          .getFilesystemPlatforms()
          .then(({ data: platforms }) => {
            this.filesystemPlatforms = platforms;
            resolve(platforms);
          })
          .catch((error) => {
            console.error(error);
            reject(error);
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
      this.filesystemPlatforms = [] as Platform[];
      this.filterText = "";
    },
  },
});
