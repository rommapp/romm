// permissionGroups — Pinia store holding the admin list of permission groups.
//
// Single source of truth shared by the groups table, the user create/edit
// dialogs and the users table, so creating or deleting a group is reflected
// everywhere immediately (no manual refetch / page refresh). Mutations go
// through `upsert` / `remove` after the API call returns.
import { defineStore } from "pinia";
import type { PermissionGroupSchema } from "@/__generated__";
import permissionsApi from "@/services/api/permissions";

export default defineStore("permissionGroups", {
  state: () => ({
    groups: [] as PermissionGroupSchema[],
    loaded: false,
    loading: false,
  }),

  getters: {
    defaultGroup: (state) => state.groups.find((g) => g.is_default),
  },

  actions: {
    /** Fetch the canonical list and replace the store. */
    async fetch() {
      this.loading = true;
      try {
        const { data } = await permissionsApi.fetchGroups();
        this.groups = data;
        this.loaded = true;
      } finally {
        this.loading = false;
      }
    },

    /** Fetch once; subsequent callers reuse the cached list. */
    async ensureLoaded() {
      if (!this.loaded && !this.loading) await this.fetch();
    },

    set(groups: PermissionGroupSchema[]) {
      this.groups = groups;
      this.loaded = true;
    },

    /** Insert a new group or replace an existing one (by id). */
    upsert(group: PermissionGroupSchema) {
      const i = this.groups.findIndex((g) => g.id === group.id);
      if (i >= 0) this.groups[i] = group;
      else this.groups = this.groups.concat(group);
    },

    remove(id: number) {
      this.groups = this.groups.filter((g) => g.id !== id);
    },

    reset() {
      this.groups = [];
      this.loaded = false;
    },
  },
});
