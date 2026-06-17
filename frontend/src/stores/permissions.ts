// permissions — Pinia store holding the current user's effective grants.
//
// Today the grants are derived from `user.role` via a hardcoded role-map
// in src/v2/composables/useCan/role-map.ts. When the backend ships
// `/permissions/me` returning normalised grants, that response replaces
// the role-derived hydration here and the role-map disappears.
//
// v2 features consume this store via `useCan(action, scope?)`. v1 does
// not import from here — its existing inline role checks keep working.
import { defineStore } from "pinia";
import type { Role } from "@/__generated__";
import { type ActionKey, type Grant } from "@/v2/composables/useCan/actions";
import { actionsForRole } from "@/v2/composables/useCan/role-map";

interface State {
  grants: Grant[];
  hydratedFromRole: Role | null;
}

export default defineStore("permissions", {
  state: (): State => ({
    grants: [],
    hydratedFromRole: null,
  }),

  actions: {
    /** Replace the stored grants with the role's blanket global grants.
     *  Temporary; replaced by setGrants once /permissions/me lands. */
    hydrateFromRole(role: Role | null) {
      if (!role) {
        this.grants = [];
        this.hydratedFromRole = null;
        return;
      }
      const actions = actionsForRole(role);
      this.grants = actions.map((action) => ({
        action,
        scope: { kind: "global" },
      }));
      this.hydratedFromRole = role;
    },

    /** Replace the stored grants with a normalised list from the backend. */
    setGrants(grants: Grant[]) {
      this.grants = grants;
      this.hydratedFromRole = null;
    },

    /** Add a single grant — useful for tests and per-resource updates. */
    addGrant(grant: Grant) {
      this.grants.push(grant);
    },

    reset() {
      this.grants = [];
      this.hydratedFromRole = null;
    },
  },

  getters: {
    actions(state): Set<ActionKey> {
      return new Set(state.grants.map((g) => g.action));
    },
  },
});
