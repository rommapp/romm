import { defineStore } from "pinia";

export default defineStore("auth", {
  state: () => ({ returnUrl: "" }),

  actions: {
    set(returnUrl) {
      this.returnUrl = returnUrl;
    },
  },
});