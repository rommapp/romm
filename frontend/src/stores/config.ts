import { defineStore } from "pinia";

import type { ConfigResponse } from "@/__generated__";

export default defineStore("config", {
  state: () => {
    return {
      config: {
        EXCLUDED_PLATFORMS: [],
        EXCLUDED_SINGLE_EXT: [],
        EXCLUDED_SINGLE_FILES: [],
        EXCLUDED_MULTI_FILES: [],
        EXCLUDED_MULTI_PARTS_EXT: [],
        EXCLUDED_MULTI_PARTS_FILES: [],
        PLATFORMS_BINDING: {},
        PLATFORMS_VERSIONS: {},
        ROMS_FOLDER_NAME: "",
        FIRMWARE_FOLDER_NAME: "",
        HIGH_PRIO_STRUCTURE_PATH: "",
      } as ConfigResponse,
    };
  },

  actions: {
    set(data: ConfigResponse) {
      this.config = data;
    },
    addPlatformBinding(fsSlug: string, slug: string) {
      this.config.PLATFORMS_BINDING[fsSlug] = slug;
    },
    removePlatformBinding(fsSlug: string) {
      delete this.config.PLATFORMS_BINDING[fsSlug];
    },
    addPlatformVersion(fsSlug: string, slug: string) {
      this.config.PLATFORMS_VERSIONS[fsSlug] = slug;
    },
    removePlatformVersion(fsSlug: string) {
      delete this.config.PLATFORMS_VERSIONS[fsSlug];
    },
  },
});
