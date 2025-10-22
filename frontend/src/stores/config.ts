import { defineStore } from "pinia";
import type { ConfigResponse, EjsControlsButton } from "@/__generated__";
import api from "@/services/api";

export type Config = ConfigResponse;
type ExclusionTypes =
  | "EXCLUDED_PLATFORMS"
  | "EXCLUDED_SINGLE_EXT"
  | "EXCLUDED_SINGLE_FILES"
  | "EXCLUDED_MULTI_FILES"
  | "EXCLUDED_MULTI_PARTS_EXT"
  | "EXCLUDED_MULTI_PARTS_FILES";

const defaultConfig = {
  CONFIG_FILE_MOUNTED: false,
  CONFIG_FILE_WRITABLE: false,
  EXCLUDED_PLATFORMS: [],
  EXCLUDED_SINGLE_EXT: [],
  EXCLUDED_SINGLE_FILES: [],
  EXCLUDED_MULTI_FILES: [],
  EXCLUDED_MULTI_PARTS_EXT: [],
  EXCLUDED_MULTI_PARTS_FILES: [],
  PLATFORMS_BINDING: {},
  PLATFORMS_VERSIONS: {},
  EJS_DEBUG: false,
  EJS_CACHE_LIMIT: null,
  EJS_SETTINGS: {},
  EJS_CONTROLS: {},
  SCAN_METADATA_PRIORITY: [],
  SCAN_ARTWORK_PRIORITY: [],
  SCAN_REGION_PRIORITY: [],
  SCAN_LANGUAGE_PRIORITY: [],
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
      const defaultOptions = this.config.EJS_SETTINGS["default"] || {};
      if (!core) return defaultOptions;
      return {
        ...defaultOptions,
        ...this.config.EJS_SETTINGS[core],
      };
    },
    getEJSControls(
      core: string | null,
    ): Record<number, Record<number, EjsControlsButton>> | null {
      const defaultControls = this.config.EJS_CONTROLS["default"];
      if (!core) {
        if (!defaultControls) return null;
        return {
          0: defaultControls["_0"] || {},
          1: defaultControls["_1"] || {},
          2: defaultControls["_2"] || {},
          3: defaultControls["_3"] || {},
        };
      }

      const coreControls = this.config.EJS_CONTROLS[core];
      if (!coreControls) return null;
      if (!defaultControls) {
        return {
          0: coreControls["_0"] || {},
          1: coreControls["_1"] || {},
          2: coreControls["_2"] || {},
          3: coreControls["_3"] || {},
        };
      }

      return {
        0: {
          ...(defaultControls["_0"] || {}),
          ...(coreControls["_0"] || {}),
        },
        1: {
          ...(defaultControls["_1"] || {}),
          ...(coreControls["_1"] || {}),
        },
        2: {
          ...(defaultControls["_2"] || {}),
          ...(coreControls["_2"] || {}),
        },
        3: {
          ...(defaultControls["_3"] || {}),
          ...(coreControls["_3"] || {}),
        },
      };
    },
    reset() {},
  },
});
