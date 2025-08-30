import { defineStore } from "pinia";
import userApi from "@/services/api/user";
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
    async fetchCurrentUser(): Promise<User | null> {
      try {
        const response = await userApi.fetchCurrentUser();
        this.user = response.data;
        return this.user;
      } catch (error) {
        console.error("Error fetching current user: ", error);
        return this.user;
      }
    },
    setCurrentUser(user: User | null) {
      this.user = user;
    },
    reset() {
      this.user = null;
      this.oauth_scopes = [];
    },
  },
});
