import { defineStore } from "pinia";

import type { HeartbeatResponse } from "@/__generated__";

export default defineStore("heartbeat", {
  state: () => {
    return { value: {} as HeartbeatResponse };
  },

  actions: {
    set(data: HeartbeatResponse) {
      this.value = data;
    },
  },
});
