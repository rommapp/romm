import { defineStore } from "pinia";

import type { HeartbeatReturn } from "@/__generated__";

export type Heartbeat = HeartbeatReturn;

export default defineStore("heartbeat", {
  state: () => ({ data: {} as Heartbeat }),

  actions: {
    set(data: Heartbeat) {
      this.data = data;
    },
    addPlatformBinding(fsSlug: string, slug: string) {
      this.data.CONFIG.PLATFORMS_BINDING[fsSlug] = slug;
    },
    removePlatformBinding(fsSlug: string) {
      delete this.data.CONFIG.PLATFORMS_BINDING[fsSlug];
    },
  },
});
