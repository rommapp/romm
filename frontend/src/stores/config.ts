import { defineStore } from "pinia";

import type { ConfigResponse } from "@/__generated__";

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
    addExclusion(exclusionValue: string, exclusionType: keyof ConfigResponse) {
      if (Array.isArray(this.config[exclusionType])) {
        (this.config[exclusionType] as string[]).push(exclusionValue);
      } else {
        console.error(`Exclusion type '${exclusionType}' is not valid`);
      }
    },
    removeExclusion(
      exclusionValue: string,
      exclusionType: keyof ConfigResponse,
    ) {
      if (Array.isArray(this.config[exclusionType])) {
        const index = (this.config[exclusionType] as string[]).indexOf(
          exclusionValue,
        );
        if (index !== -1) {
          (this.config[exclusionType] as string[]).splice(index, 1);
        } else {
          console.error(
            `Value '${exclusionValue}' not found in '${exclusionType}'.`,
          );
        }
      } else {
        console.error(`Exclusion type '${exclusionType}' is not valid`);
      }
    },
  },
});
