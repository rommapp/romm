import type { HeartbeatResponse } from "@/__generated__";
import { defineStore } from "pinia";
import { computed } from "vue";

export default defineStore(
  "heartbeat",
  {
    state: () => {
      return {
        value: {
          VERSION: "",
          GITHUB_VERSION: "",
          ANY_SOURCE_ENABLED: false,
          METADATA_SOURCES: {
            IGDB_API_ENABLED: false,
            MOBY_API_ENABLED: false,
          },
          WATCHER: {
            ENABLED: false,
            TITLE: "Rescan on filesystem change",
            MESSAGE:
              "Runs a scan when a change is detected in the library path, with a delay",
          },
          SCHEDULER: {
            RESCAN: {
              ENABLED: false,
              CRON: "",
              TITLE: "Scheduled rescan",
              MESSAGE: "Rescans the entire library",
            },
            SWITCH_TITLEDB: {
              ENABLED: false,
              CRON: "",
              TITLE: "Scheduled Switch TitleDB update",
              MESSAGE: "Updates the Nintendo Switch TitleDB file",
            },
          },
        },
      };
    },

    actions: {
      set(data: HeartbeatResponse) {
        this.value = { ...this.value, ...data };

        fetch("https://api.github.com/repos/rommapp/romm/releases/latest").then(
          async (response) => {
            const json = await response.json();
            this.value.GITHUB_VERSION = json.name;
          }
        );
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
        ]).value.filter((s) => !s.disabled);
      },
    },
  }
);
