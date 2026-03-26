import { defineStore } from "pinia";
import userApi from "@/services/api/user";
import type { User } from "./users";

export default defineStore("auth", {
  state: () => ({
    user: null as User | null,
    oauth_scopes: [] as string[],
    isLoading: false,
    errorMessage: null as string | null,
  }),

  getters: {
    scopes: (state) => {
      return state.user?.oauth_scopes ?? [];
    },
  },

  actions: {
    async fetchCurrentUser(): Promise<User | null> {
      this.isLoading = true;
      this.errorMessage = null;

      try {
        const response = await userApi.fetchCurrentUser();
        this.user = response.data;
        this.errorMessage = null;
        return this.user;
      } catch (error) {
        console.error("Error fetching current user: ", error);
        this.errorMessage = "Unable to load session. Please sign in again.";
        return this.user;
      } finally {
        this.isLoading = false;
      }
    },
    setCurrentUser(user: User | null) {
      this.user = user;
    },
    reset() {
      this.user = null;
      this.oauth_scopes = [];
      this.isLoading = false;
      this.errorMessage = null;
    },
  },
});
