import { defineStore } from "pinia";

import type { User } from "./users";

export default defineStore("auth", {
  state: () => ({
    user: null as User | null,
    oauth_scopes: [] as string[],
  }),

  getters: {
    scopes: (state) => {
      return state.user?.oauth_scopes ?? [];
    },
  },

  actions: {
    setUser(user: User | null) {
      this.user = user;
    },
  },
});
