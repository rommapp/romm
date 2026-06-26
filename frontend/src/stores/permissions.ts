// permissions — Pinia store holding the current user's effective grants.
//
// Hydrated from the backend's `/permissions/me` (the source of truth) via
// `installPermissionsHydration()` in AppLayout, and refreshed live on the
// `permissions:changed` socket event. v2 features consume this store via
// `useCan(action, scope?)`. v1 does not import from here — its existing inline
// scope checks keep working.
import { defineStore } from "pinia";
import type {
  PermissionScopeSchema,
  PermissionsResponse,
} from "@/__generated__";
import {
  type ActionKey,
  type Grant,
  type PermissionScope,
} from "@/v2/composables/useCan/actions";

interface State {
  grants: Grant[];
  isAdmin: boolean;
  hidden: { platforms: number[]; roms: number[] };
}

function normalizeScope(scope: PermissionScopeSchema): PermissionScope {
  if (!scope.kind || scope.kind === "global") return { kind: "global" };
  return { kind: scope.kind, id: scope.id ?? 0 };
}

export default defineStore("permissions", {
  state: (): State => ({
    grants: [],
    isAdmin: false,
    hidden: { platforms: [], roms: [] },
  }),

  actions: {
    /** Replace the stored permissions with the `/permissions/me` response. */
    hydrateFromResponse(payload: PermissionsResponse) {
      this.grants = payload.grants.map((g) => ({
        action: g.action,
        scope: normalizeScope(g.scope),
      }));
      this.isAdmin = payload.is_admin;
      this.hidden = {
        platforms: [...payload.hidden.platforms],
        roms: [...payload.hidden.roms],
      };
    },

    /** Seed a clean non-admin state with the given grants (tests/stories).
     * Resets isAdmin/hidden too so a prior hydration can't leak through. */
    setGrants(grants: Grant[]) {
      this.grants = grants;
      this.isAdmin = false;
      this.hidden = { platforms: [], roms: [] };
    },

    reset() {
      this.grants = [];
      this.isAdmin = false;
      this.hidden = { platforms: [], roms: [] };
    },
  },

  getters: {
    actions(state): Set<ActionKey> {
      return new Set(state.grants.map((g) => g.action));
    },
  },
});
