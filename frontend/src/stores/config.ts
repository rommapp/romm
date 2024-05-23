import { defineStore } from "pinia";

import type { ConfigResponse } from "@/__generated__";

export default defineStore("config", {
  state: () => {
    return {
      value: {
        EXCLUDED_PLATFORMS: [] as string[],
        EXCLUDED_SINGLE_EXT: [] as string[],
        EXCLUDED_SINGLE_FILES: [] as string[],
        EXCLUDED_MULTI_FILES: [] as string[],
        EXCLUDED_MULTI_PARTS_EXT: [] as string[],
        EXCLUDED_MULTI_PARTS_FILES: [] as string[],
        PLATFORMS_BINDING: {} as Record<string, string>,
        PLATFORMS_VERSIONS: {} as Record<string, string>,
        ROMS_FOLDER_NAME: "",
        FIRMWARE_FOLDER_NAME: "",
        HIGH_PRIO_STRUCTURE_PATH: "",
      },
    };
  },

  actions: {
    set(data: ConfigResponse) {
      this.value = data;
    },
    addPlatformBinding(fsSlug: string, slug: string) {
      this.value.PLATFORMS_BINDING[fsSlug] = slug;
    },
    removePlatformBinding(fsSlug: string) {
      delete this.value.PLATFORMS_BINDING[fsSlug];
    },
    addPlatformVersion(fsSlug: string, slug: string) {
      this.value.PLATFORMS_VERSIONS[fsSlug] = slug;
    },
    removePlatformVersion(fsSlug: string) {
      delete this.value.PLATFORMS_VERSIONS[fsSlug];
    },
  },
});
