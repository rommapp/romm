import type {
  SmbAccessMode,
  SmbLogsSchema,
  SmbStatusSchema,
  SmbUserSchema,
  SmbUserSecretSchema,
} from "@/__generated__";
import api from "@/services/api";

export interface SmbPermissionInput {
  platform_id: number;
  access: SmbAccessMode;
}

async function getStatus() {
  return api.get<SmbStatusSchema>("/smb/status");
}

async function getUsers() {
  return api.get<SmbUserSchema[]>("/smb/users");
}

async function startService() {
  return api.post<SmbStatusSchema>("/smb/start");
}

async function restartService() {
  return api.post<SmbStatusSchema>("/smb/restart");
}

async function getLogs(lines = 200) {
  return api.get<SmbLogsSchema>("/smb/logs", { params: { lines } });
}

async function createUser(payload: {
  username: string;
  permissions: SmbPermissionInput[];
}) {
  return api.post<SmbUserSecretSchema>("/smb/users", payload);
}

async function updateUser(userId: number, permissions: SmbPermissionInput[]) {
  return api.put<SmbUserSchema>(`/smb/users/${userId}`, { permissions });
}

async function rotateUser(userId: number) {
  return api.post<SmbUserSecretSchema>(`/smb/users/${userId}/rotate`);
}

async function deleteUser(userId: number) {
  return api.delete(`/smb/users/${userId}`);
}

async function syncConfig() {
  return api.post("/smb/sync");
}

export default {
  getStatus,
  startService,
  restartService,
  getLogs,
  getUsers,
  createUser,
  updateUser,
  rotateUser,
  deleteUser,
  syncConfig,
};
