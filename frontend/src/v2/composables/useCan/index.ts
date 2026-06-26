// useCan — reactive permission check against the v2 permissions store.
//
//   useCan('rom.upload')                         — global "anywhere" check.
//   useCan('rom.upload', { kind: 'platform', id: 5 })
//                                                — scoped to a single resource.
//
// Returns ComputedRef<boolean>. Admins short-circuit to true; otherwise false
// when no matching grant is present (and when no user is authenticated). Reads
// from `permissionsStore`, hydrated from the backend's /permissions/me.
//
// Frontend is a UX hint, never the authority — the backend remains the source
// of truth and rejects unauthorised actions regardless of what the UI showed.
import { storeToRefs } from "pinia";
import { computed, type ComputedRef, watch } from "vue";
import permissionsService from "@/services/api/permissions";
import storeAuth from "@/stores/auth";
import storePermissions from "@/stores/permissions";
import { useSocketEvent } from "@/v2/composables/useSocketEvent";
import type { ActionKey, Grant, PermissionScope } from "./actions";

export type { ActionKey, Grant, PermissionScope };

/** Mount-time helper: keep permissionsStore in sync with the current user by
 *  fetching /permissions/me on login and on the `permissions:changed` socket
 *  event. Call once high in the v2 tree (AppLayout) — the watch is idempotent. */
export function installPermissionsHydration() {
  const auth = storeAuth();
  const permissions = storePermissions();
  const { user } = storeToRefs(auth);

  async function refresh() {
    try {
      const { data } = await permissionsService.fetchMyPermissions();
      permissions.hydrateFromResponse(data);
    } catch {
      // The axios interceptor handles auth errors; clear grants so nothing
      // stays gated-open after a failed refresh.
      permissions.reset();
    }
  }

  watch(
    user,
    (u) => {
      if (u) refresh();
      else permissions.reset();
    },
    { immediate: true },
  );

  // The backend broadcasts on any permission change; refresh when it's ours.
  useSocketEvent<{ user_id: number }>("permissions:changed", (payload) => {
    if (user.value && payload.user_id === user.value.id) refresh();
  });
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
    if (permissions.isAdmin) return true;
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
