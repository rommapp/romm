import { defineStore } from "pinia";

import type { ConfigResponse } from "@/__generated__";

type ExclusionTypes =
  | "EXCLUDED_PLATFORMS"
  | "EXCLUDED_SINGLE_EXT"
  | "EXCLUDED_SINGLE_FILES"
  | "EXCLUDED_MULTI_FILES"
  | "EXCLUDED_MULTI_PARTS_EXT"
  | "EXCLUDED_MULTI_PARTS_FILES";

export default defineStore("config", {
  state: () => {
    return {
      config: {
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
    addExclusion(exclusionType: ExclusionTypes, exclusionValue: string) {
      this.config[exclusionType].push(exclusionValue);
    },
    removeExclusion(exclusionValue: string, exclusionType: ExclusionTypes) {
      const index = this.config[exclusionType].indexOf(exclusionValue);
      if (index !== -1) {
        this.config[exclusionType].splice(index, 1);
      } else {
        console.error(
          `Value '${exclusionValue}' not found in exclusion type '${exclusionType}'`,
        );
      }
    },
    isExclusionType(type: string): type is ExclusionTypes {
      return Object.keys(this.config).includes(type);
    },
  },
});
