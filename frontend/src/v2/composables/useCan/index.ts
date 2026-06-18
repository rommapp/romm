// useCan — reactive permission check against the v2 permissions store.
//
//   useCan('rom.upload')                         — global "anywhere" check.
//   useCan('rom.upload', { kind: 'platform', id: 5 })
//                                                — scoped to a single resource.
//
// Returns ComputedRef<boolean>. False when no user is authenticated. Reads
// from `permissionsStore.grants`, which today is derived from the user's
// role via a hardcoded role-map. Once the backend ships /permissions/me,
// the store hydrates directly from the response and this composable is
// unchanged.
//
// Frontend is a UX hint, never the authority — the backend remains the
// source of truth and rejects unauthorised actions regardless of what the
// UI showed.
import { storeToRefs } from "pinia";
import { computed, type ComputedRef, watch } from "vue";
import storeAuth from "@/stores/auth";
import storePermissions from "@/stores/permissions";
import type { ActionKey, Grant, PermissionScope } from "./actions";

export type { ActionKey, Grant, PermissionScope };

/** Mount-time helper: keep permissionsStore in sync with the current user's
 *  role until the backend ships /permissions/me. Call once high in the
 *  v2 tree (AppLayout) — safe to call multiple times, the watch is idempotent. */
export function installPermissionsHydration() {
  const auth = storeAuth();
  const permissions = storePermissions();
  const { user } = storeToRefs(auth);
  watch(
    user,
    (u) => {
      permissions.hydrateFromRole(u?.role ?? null);
    },
    { immediate: true },
  );
}

function scopeMatches(
  grantScope: PermissionScope,
  asked: PermissionScope,
): boolean {
  if (grantScope.kind === "global") return true;
  if (grantScope.kind !== asked.kind) return false;
  // Both are non-global same kind — the IDs must match.
  return (grantScope as { id: number }).id === (asked as { id: number }).id;
}

export function useCan(
  action: ActionKey,
  scope?: PermissionScope,
): ComputedRef<boolean> {
  const permissions = storePermissions();
  return computed(() => {
    const asked: PermissionScope = scope ?? { kind: "global" };
    for (const grant of permissions.grants) {
      if (grant.action !== action) continue;
      if (asked.kind === "global") {
        // "Can do this anywhere?" — any scope of grant satisfies.
        return true;
      }
      if (scopeMatches(grant.scope, asked)) return true;
    }
    return false;
  });
}
