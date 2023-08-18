import { defineStore } from "pinia";

export default defineStore("auth", {
  state: () => ({ user: null }),

  actions: {
    setUser(user) {
      this.user = user;
    },
  },
});
