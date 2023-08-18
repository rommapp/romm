import { defineStore } from "pinia";

export default defineStore("auth", {
  state: () => ({ enabled: false, user: null }),

  actions: {
    setUser(user) {
      this.user = user;
    },
    setEnabled(enabled) {
      this.enabled = enabled;
    },
  },
});
