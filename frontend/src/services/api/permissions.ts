import type {
  Body_remove_hidden_entity_api_permissions_hidden_delete as RemoveHiddenBody,
  HiddenEntityCreate,
  HiddenEntitySchema,
  PermissionCatalogSchema,
  PermissionGroupCreate,
  PermissionGroupSchema,
  PermissionGroupUpdate,
  PermissionsResponse,
  UserPermissionsSchema,
  UserPermissionsUpdate,
} from "@/__generated__";
import api from "@/services/api";

// The caller's effective permissions (granted action keys + hidden ids). The
// backend is the source of truth; the UI uses this only to gate what it shows.
async function fetchMyPermissions() {
  return api.get<PermissionsResponse>("/permissions/me");
}

// --- Admin: catalog + groups -------------------------------------------------

async function fetchCatalog() {
  return api.get<PermissionCatalogSchema>("/permissions/catalog");
}

async function fetchGroups() {
  return api.get<PermissionGroupSchema[]>("/permissions/groups");
}

async function createGroup(body: PermissionGroupCreate) {
  return api.post<PermissionGroupSchema>("/permissions/groups", body);
}

async function updateGroup(id: number, body: PermissionGroupUpdate) {
  return api.put<PermissionGroupSchema>(`/permissions/groups/${id}`, body);
}

async function deleteGroup(id: number) {
  return api.delete(`/permissions/groups/${id}`);
}

// --- Admin: per-user assignment + hiding -------------------------------------

async function fetchUserPermissions(userId: number) {
  return api.get<UserPermissionsSchema>(`/permissions/users/${userId}`);
}

async function updateUserPermissions(
  userId: number,
  body: UserPermissionsUpdate,
) {
  return api.put<UserPermissionsSchema>(`/permissions/users/${userId}`, body);
}

async function addHiddenEntity(body: HiddenEntityCreate) {
  return api.post<HiddenEntitySchema>("/permissions/hidden", body);
}

async function removeHiddenEntity(body: RemoveHiddenBody) {
  return api.delete("/permissions/hidden", { data: body });
}

export default {
  fetchMyPermissions,
  fetchCatalog,
  fetchGroups,
  createGroup,
  updateGroup,
  deleteGroup,
  fetchUserPermissions,
  updateUserPermissions,
  addHiddenEntity,
  removeHiddenEntity,
};
