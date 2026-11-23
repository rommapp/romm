import type {
  InstallRequestCreatePayload,
  InstallRequestSchema,
} from "@/__generated__";
import api from "@/services/api";

async function fetchRomInstalls(romId: number) {
  return api.get<InstallRequestSchema[]>(`/roms/${romId}/installs`);
}

async function createInstall(
  deviceId: string,
  payload: InstallRequestCreatePayload,
) {
  return api.post<InstallRequestSchema>(
    `/devices/${encodeURIComponent(deviceId)}/installs`,
    payload,
  );
}

async function cancelInstall(deviceId: string, requestId: string) {
  return api.delete<InstallRequestSchema>(
    `/devices/${encodeURIComponent(deviceId)}/installs/${encodeURIComponent(requestId)}`,
  );
}

export default {
  fetchRomInstalls,
  createInstall,
  cancelInstall,
};
