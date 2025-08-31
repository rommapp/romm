import type { HeartbeatResponse } from "@/__generated__";
import { defineStore } from "pinia";
import i18n from "@/locales";
import api from "@/services/api";

export type Heartbeat = HeartbeatResponse;
export type MetadataOption = {
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
    YOUTUBE_BASE_URL: "https://www.youtube.com",
  },
  OIDC: {
    ENABLED: false,
    PROVIDER: "",
  },
  TASKS: {
    ENABLE_SCHEDULED_RESCAN: false,
    SCHEDULED_RESCAN_CRON: "",
    ENABLE_SCHEDULED_UPDATE_SWITCH_TITLEDB: false,
    SCHEDULED_UPDATE_SWITCH_TITLEDB_CRON: "",
    ENABLE_SCHEDULED_UPDATE_LAUNCHBOX_METADATA: false,
    SCHEDULED_UPDATE_LAUNCHBOX_METADATA_CRON: "",
    ENABLE_SCHEDULED_CONVERT_IMAGES_TO_WEBP: false,
    SCHEDULED_CONVERT_IMAGES_TO_WEBP_CRON: "",
  },
};

export default defineStore("heartbeat", {
  state: () => ({
    value: { ...defaultHeartbeat },
  }),

  actions: {
    async fetchHeartbeat(): Promise<Heartbeat> {
      try {
        const response = await api.get("/heartbeat");
        this.value = { ...this.value, ...response.data };
        return this.value;
      } catch (error) {
        console.error("Error fetching heartbeat: ", error);
        return this.value;
      }
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
          name: "Hasheous",
          value: "hasheous",
          logo_path: "/assets/scrappers/hasheous.png",
          disabled: !this.value.METADATA_SOURCES?.HASHEOUS_API_ENABLED
            ? i18n.global.t("scan.disabled-by-admin")
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
          name: "Mobygames",
          value: "moby",
          logo_path: "/assets/scrappers/moby.png",
          disabled: !this.value.METADATA_SOURCES?.MOBY_API_ENABLED
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
          name: "SteamGridDB",
          value: "sgdb",
          logo_path: "/assets/scrappers/sgdb.png",
          disabled: !this.value.METADATA_SOURCES?.STEAMGRIDDB_API_ENABLED
            ? i18n.global.t("scan.api-key-missing")
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
