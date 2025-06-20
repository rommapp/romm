import type { HeartbeatResponse } from "@/__generated__";
import { defineStore } from "pinia";
import i18n from "@/locales";

export type Heartbeat = HeartbeatResponse;
type MetadataOption = {
  name: string;
  value: string;
  logo_path: string;
  disabled: string;
};

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
    LAUNCHBOX_METADATA: {
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
    LAUNCHBOX_API_ENABLED: false,
    PLAYMATCH_API_ENABLED: false,
    HASHEOUS_API_ENABLED: false,
    TGDB_API_ENABLED: false,
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

    getAllMetadataOptions(): MetadataOption[] {
      return [
        {
          name: this.value.METADATA_SOURCES?.PLAYMATCH_API_ENABLED
            ? "IGDB + Playmatch"
            : "IGDB",
          value: "igdb",
          logo_path: "/assets/scrappers/igdb.png",
          disabled: !this.value.METADATA_SOURCES?.IGDB_API_ENABLED
            ? i18n.global.t("scan.api-key-missing")
            : "",
        },
        {
          name: "Mobygames",
          value: "moby",
          logo_path: "/assets/scrappers/moby.png",
          disabled: !this.value.METADATA_SOURCES?.MOBY_API_ENABLED
            ? i18n.global.t("scan.api-key-missing")
            : "",
        },
        {
          name: "Screenscraper",
          value: "ss",
          logo_path: "/assets/scrappers/ss.png",
          disabled: !this.value.METADATA_SOURCES?.SS_API_ENABLED
            ? i18n.global.t("scan.api-key-missing")
            : "",
        },
        {
          name: "RetroAchievements",
          value: "ra",
          logo_path: "/assets/scrappers/ra.png",
          disabled: !this.value.METADATA_SOURCES?.RA_API_ENABLED
            ? i18n.global.t("scan.api-key-missing")
            : "",
        },
        {
          name: "Launchbox",
          value: "lb",
          logo_path: "/assets/scrappers/launchbox.png",
          disabled: !this.value.METADATA_SOURCES?.LAUNCHBOX_API_ENABLED
            ? i18n.global.t("scan.disabled-by-admin")
            : "",
        },
        {
          name: "Hasheous",
          value: "hasheous",
          logo_path: "/assets/scrappers/hasheous.png",
          disabled: !this.value.METADATA_SOURCES?.HASHEOUS_API_ENABLED
            ? i18n.global.t("scan.disabled-by-admin")
            : "",
        },
      ];
    },
    getEnabledMetadataOptions(): MetadataOption[] {
      return this.getAllMetadataOptions().filter((s) => !s.disabled);
    },
    reset() {},
  },
});
