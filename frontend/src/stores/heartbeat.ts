import { defineStore } from "pinia";
import type { HeartbeatResponse } from "@/__generated__";
import i18n from "@/locales";
import api from "@/services/api";
import storeConfig from "./config";

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
    FLASHPOINT_API_ENABLED: false,
    HLTB_API_ENABLED: false,
    LIBRETRO_API_ENABLED: false,
  },
  FILESYSTEM: {
    FS_PLATFORMS: [],
  },
  EMULATION: {
    DISABLE_EMULATOR_JS: false,
    DISABLE_RUFFLE_RS: false,
  },
  FRONTEND: {
    DISABLE_USERPASS_LOGIN: false,
    DISABLE_LOGS_VIEWER: false,
    YOUTUBE_BASE_URL: "https://www.youtube.com",
  },
  OIDC: {
    ENABLED: false,
    AUTOLOGIN: false,
    PROVIDER: "",
    RP_INITIATED_LOGOUT: false,
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
    // Whether the backend is currently healthy. Optimistic by default so the
    // offline UI never flashes before the first request resolves. The
    // heartbeat is the authoritative health check: a 5xx or a missing response
    // (ERR_NETWORK / timeout) means the backend is down/broken; a 4xx still
    // means it's alive (auth / validation). Consumed by the v2 offline banner
    // and by the router guard so a broken backend isn't mistaken for "logged
    // out, setup already done".
    connected: true,
  }),

  actions: {
    async fetchHeartbeat(options?: { timeout?: number }): Promise<Heartbeat> {
      try {
        const response = await api.get("/heartbeat", options);
        this.value = { ...this.value, ...response.data };
        this.connected = true;
        return this.value;
      } catch (error) {
        // 5xx or no response (network/timeout) → backend is down/broken.
        // 4xx → backend is alive (auth/validation), so still "connected".
        const status = (error as { response?: { status?: number } }).response
          ?.status;
        const nowConnected = status !== undefined && status < 500;
        // Log only a genuine breakage, and only on the connected→disconnected
        // transition: this heartbeat polls every few seconds while offline, so
        // logging every failure would bury actionable errors. A 4xx is a
        // healthy backend, not an error worth reporting here.
        if (!nowConnected && this.connected) {
          console.error("Error fetching heartbeat: ", error);
        }
        this.connected = nowConnected;
        return this.value;
      }
    },

    setConnected(value: boolean) {
      this.connected = value;
    },

    async fetchMetadataHeartbeat(source: string): Promise<boolean> {
      try {
        const response = await api.get(`/heartbeat/metadata/${source}`);
        return response.data;
      } catch (error) {
        console.error("Error fetching metadata heartbeat: ", error);
        return false;
      }
    },

    getAllMetadataOptions(): MetadataOption[] {
      return [
        {
          name: "IGDB",
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
          name: "Playmatch",
          value: "playmatch",
          logo_path: "/assets/scrappers/playmatch.png",
          disabled: !this.value.METADATA_SOURCES?.PLAYMATCH_API_ENABLED
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
          value: "launchbox",
          logo_path: "/assets/scrappers/launchbox.png",
          disabled: !this.value.METADATA_SOURCES?.LAUNCHBOX_API_ENABLED
            ? i18n.global.t("scan.disabled-by-admin")
            : "",
        },
        {
          name: "Flashpoint Project",
          value: "flashpoint",
          logo_path: "/assets/scrappers/flashpoint.png",
          disabled: !this.value.METADATA_SOURCES?.FLASHPOINT_API_ENABLED
            ? i18n.global.t("scan.api-key-missing")
            : "",
        },
        {
          name: "HowLongToBeat",
          value: "hltb",
          logo_path: "/assets/scrappers/hltb.png",
          disabled: !this.value.METADATA_SOURCES?.HLTB_API_ENABLED
            ? i18n.global.t("scan.api-key-missing")
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
        {
          name: "ES-DE (gamelist.xml)",
          value: "gamelist",
          logo_path: "/assets/scrappers/esde.png",
          disabled: "",
        },
        {
          name: "Libretro",
          value: "libretro",
          logo_path: "/assets/scrappers/libretro.png",
          disabled: !this.value.METADATA_SOURCES?.LIBRETRO_API_ENABLED
            ? i18n.global.t("scan.disabled-by-admin")
            : "",
        },
      ];
    },
    getEnabledMetadataOptions(): MetadataOption[] {
      return this.getAllMetadataOptions().filter((s) => !s.disabled);
    },
    getMetadataOptionsByPriority(): MetadataOption[] {
      const allOptions = this.getAllMetadataOptions();
      const { config } = storeConfig();
      const priority = config.SCAN_METADATA_PRIORITY || [];

      // Create a map for quick lookup
      const optionsMap = new Map(
        allOptions.map((option) => [option.value, option]),
      );

      // Get options in priority order
      const priorityOrdered = priority
        .map((value: string) => optionsMap.get(value))
        .filter(Boolean) as MetadataOption[];

      // Add remaining options that weren't in priority list
      const remaining = allOptions.filter(
        (option) => !priority.includes(option.value),
      );

      return [...priorityOrdered, ...remaining];
    },
    reset() {},
  },
});
