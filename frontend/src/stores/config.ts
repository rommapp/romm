import { defineStore } from "pinia";

import type { ConfigResponse, EjsControlsButton } from "@/__generated__";
import api from "@/services/api";

type ExclusionTypes =
  | "EXCLUDED_PLATFORMS"
  | "EXCLUDED_SINGLE_EXT"
  | "EXCLUDED_SINGLE_FILES"
  | "EXCLUDED_MULTI_FILES"
  | "EXCLUDED_MULTI_PARTS_EXT"
  | "EXCLUDED_MULTI_PARTS_FILES";

const defaultConfig = {
  EXCLUDED_PLATFORMS: [],
  EXCLUDED_SINGLE_EXT: [],
  EXCLUDED_SINGLE_FILES: [],
  EXCLUDED_MULTI_FILES: [],
  EXCLUDED_MULTI_PARTS_EXT: [],
  EXCLUDED_MULTI_PARTS_FILES: [],
  PLATFORMS_BINDING: {},
  PLATFORMS_VERSIONS: {},
  EJS_DEBUG: false,
  EJS_OPTIONS: {},
  EJS_CONTROLS: {},
} as ConfigResponse;

export default defineStore("config", {
  state: () => ({
    config: { ...defaultConfig },
  }),

  actions: {
    async fetchConfig(): Promise<ConfigResponse> {
      try {
        const response = await api.get("/config");
        this.config = response.data;
        return this.config;
      } catch (error) {
        console.error("Error fetching config: ", error);
        return this.config;
      }
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
    getEJSCoreOptions(core: string | null): Record<string, string | boolean> {
      const defaultOptions = this.config.EJS_OPTIONS["default"] || {};
      if (!core) return defaultOptions;
      return {
        ...defaultOptions,
        ...this.config.EJS_OPTIONS[core],
      };
    },
    getEJSControls(
      core: string | null,
    ): Record<number, Record<number, EjsControlsButton>> {
      const defaultControls = {
        0: this.config.EJS_CONTROLS["default"]?.["_0"] || {},
        1: this.config.EJS_CONTROLS["default"]?.["_1"] || {},
        2: this.config.EJS_CONTROLS["default"]?.["_2"] || {},
        3: this.config.EJS_CONTROLS["default"]?.["_3"] || {},
      };
      if (!core) return defaultControls;

      return {
        0: {
          ...(this.config.EJS_CONTROLS[core]?.["_0"] || {}),
          ...defaultControls[0],
        },
        1: {
          ...(this.config.EJS_CONTROLS[core]?.["_1"] || {}),
          ...defaultControls[1],
        },
        2: {
          ...(this.config.EJS_CONTROLS[core]?.["_2"] || {}),
          ...defaultControls[2],
        },
        3: {
          ...(this.config.EJS_CONTROLS[core]?.["_3"] || {}),
          ...defaultControls[3],
        },
      };
    },
    reset() {},
  },
});
