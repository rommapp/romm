import type { PermissionsResponse } from "@/__generated__";
import api from "@/services/api";

export const permissionsApi = api;

// The caller's effective permissions (granted action keys + hidden ids). The
// backend is the source of truth; the UI uses this only to gate what it shows.
async function fetchMyPermissions() {
  return api.get<PermissionsResponse>("/permissions/me");
}

export default { fetchMyPermissions };
