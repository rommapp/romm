import { defineStore } from "pinia";

import type { HeartbeatReturn } from "@/__generated__";

export type Heartbeat = HeartbeatReturn;

export default defineStore("heartbeat", {
  state: () => ({ data: {} as Heartbeat }),

  actions: {
    set(data: Heartbeat) {
      this.data = data;
    }
  },
});
