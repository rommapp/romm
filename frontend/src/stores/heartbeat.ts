import type { HeartbeatResponse } from "@/__generated__";
import { defineStore } from "pinia";
import { computed } from "vue";

export type Heartbeat = HeartbeatResponse;

const defaultHeartbeat: Heartbeat = {
  SYSTEM: {
    VERSION: "0.0.0",
    SHOW_SETUP_WIZARD: false,
  },
  WATCHER: {
    ENABLED: false,
    TITLE: "",
    MESSAGE: "",
  },
  SCHEDULER: {
    RESCAN: {
      ENABLED: false,
      TITLE: "",
      MESSAGE: "",
      CRON: "",
    },
    SWITCH_TITLEDB: {
      ENABLED: false,
      TITLE: "",
      MESSAGE: "",
      CRON: "",
    },
  },
  METADATA_SOURCES: {
    ANY_SOURCE_ENABLED: false,
    IGDB_API_ENABLED: false,
    SS_API_ENABLED: false,
    MOBY_API_ENABLED: false,
    RA_API_ENABLED: false,
    STEAMGRIDDB_API_ENABLED: false,
  },
  FILESYSTEM: {
    FS_PLATFORMS: [],
  },
  EMULATION: {
    DISABLE_EMULATOR_JS: false,
    DISABLE_RUFFLE_RS: false,
  },
  FRONTEND: {
    UPLOAD_TIMEOUT: 20,
    DISABLE_USERPASS_LOGIN: false,
  },
  OIDC: {
    ENABLED: false,
    PROVIDER: "",
  },
};

export default defineStore("heartbeat", {
  state: () => ({
    value: { ...defaultHeartbeat },
  }),

  actions: {
    set(data: HeartbeatResponse) {
      this.value = { ...this.value, ...data };
    },
    getMetadataOptions() {
      return computed(() => [
        {
          name: "IGDB",
          value: "igdb",
          disabled: !this.value.METADATA_SOURCES?.IGDB_API_ENABLED,
        },
        {
          name: "MobyGames",
          value: "moby",
          disabled: !this.value.METADATA_SOURCES?.MOBY_API_ENABLED,
        },
        {
          name: "Screenscraper",
          value: "ss",
          disabled: !this.value.METADATA_SOURCES?.SS_API_ENABLED,
        },
        {
          name: "RetroAchievements",
          value: "ra",
          disabled: !this.value.METADATA_SOURCES?.RA_API_ENABLED,
        },
      ]).value.filter((s) => !s.disabled);
    },
    reset() {},
  },
});
