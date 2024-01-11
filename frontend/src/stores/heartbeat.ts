import { defineStore } from "pinia";

import type { HeartbeatReturn } from "@/__generated__";

export type Heartbeat = HeartbeatReturn;

export default defineStore("heartbeat", {
  state: () => ({ data: {} as Heartbeat }),

  actions: {
    set(data: Heartbeat) {
      this.data = data;
    },
    removePlatformBinding(fs_slug: string) {
      delete this.data.CONFIG.PLATFORMS_BINDING[fs_slug];
    },
  },
});
