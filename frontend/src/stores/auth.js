import { defineStore } from "pinia";

const FULL_SCOPES_LIST = [
  "me.read",
  "me.write",
  "roms.read",
  "roms.write",
  "platforms.read",
  "platforms.write",
  "users.read",
  "users.write",
];

export default defineStore("auth", {
  state: () => ({ enabled: false, user: null, oauth_scopes: [] }),

  getters: {
    scopes: (state) => {
      if (!state.enabled) return FULL_SCOPES_LIST;
      return state.user?.oauth_scopes ?? [];
    },
  },

  actions: {
    setUser(user) {
      this.user = user;
    },
    setEnabled(enabled) {
      this.enabled = enabled;
    },
  },
});
