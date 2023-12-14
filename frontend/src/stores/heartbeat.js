import { defineStore } from "pinia";

export default defineStore("heartbeat", {
  state: () => ({ data: {} }),

  actions: {
    set(data) {
      this.data = data;
    }
  },
});
