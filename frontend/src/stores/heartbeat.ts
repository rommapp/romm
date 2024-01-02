import { defineStore } from "pinia";

export type Heartbeat = {
  VERSION: string;
  ROMM_AUTH_ENABLED: boolean;
  WATCHER: {
    ENABLED: boolean;
    TITLE: string;
  };
  SCHEDULER: {
    RESCAN: {
      ENABLED: boolean;
      CRON: string;
      TITLE: string;
    };
    SWITCH_TITLEDB: {
      ENABLED: boolean;
      CRON: string;
      TITLE: string;
    };
    MAME_XML: {
      ENABLED: boolean;
      CRON: string;
      TITLE: string;
    };
  };
  CONFIG: {
    EXCLUDED_MULTI_FILES: string[];
    EXCLUDED_SINGLE_EXT: string[];
  };
};

export default defineStore("heartbeat", {
  state: () => ({ data: {} as Heartbeat }),

  actions: {
    set(data: Heartbeat) {
      this.data = data;
    }
  },
});
