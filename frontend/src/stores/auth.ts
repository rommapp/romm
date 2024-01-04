import { defineStore } from "pinia";

import type { User } from "./users";

const FULL_SCOPES_LIST = [
  "me.read",
  "me.write",
  "roms.read",
  "roms.write",
  "platforms.read",
  "platforms.write",
  "users.read",
  "users.write",
  "tasks.run",
] as const;

export default defineStore("auth", {
  state: () => ({ enabled: false, user: null as User | null, oauth_scopes: [] as string[] }),

  getters: {
    scopes: (state) => {
      if (!state.enabled) return FULL_SCOPES_LIST;
      return state.user?.oauth_scopes ?? [];
    },
  },

  actions: {
    setUser(user: User | null) {
      this.user = user;
    },
    setEnabled(enabled: boolean) {
      this.enabled = enabled;
    },
  },
});
