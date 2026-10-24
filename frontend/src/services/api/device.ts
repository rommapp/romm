import type {
  DeviceSchema,
  DeviceUpdatePayload,
  ConsoleCreatePayload,
  ConsoleProbePayload,
  ConsoleProbeResponse,
  ConsoleUpdatePayload,
  SyncSessionSchema,
} from "@/__generated__";
import api from "@/services/api";

async function fetchDevices() {
  return api.get<DeviceSchema[]>("/devices");
}

async function fetchOnlineDeviceIds() {
  return api.get<string[]>("/devices/online");
}

async function updateDevice(id: string, payload: DeviceUpdatePayload) {
  return api.put<DeviceSchema>(`/devices/${encodeURIComponent(id)}`, payload);
}

async function deleteDevice(id: string) {
  return api.delete(`/devices/${encodeURIComponent(id)}`);
}

async function addConsole(payload: ConsoleCreatePayload) {
  return api.post<DeviceSchema>("/devices/consoles", payload);
}

async function updateConsole(id: string, payload: ConsoleUpdatePayload) {
  return api.put<DeviceSchema>(
    `/devices/consoles/${encodeURIComponent(id)}`,
    payload,
  );
}

async function probeConsole(payload: ConsoleProbePayload) {
  return api.post<ConsoleProbeResponse>("/devices/consoles/probe", payload);
}

async function syncConsole(id: string) {
  return api.post<SyncSessionSchema>(
    `/devices/consoles/${encodeURIComponent(id)}/sync`,
  );
}

export default {
  fetchDevices,
  fetchOnlineDeviceIds,
  updateDevice,
  deleteDevice,
  addConsole,
  updateConsole,
  probeConsole,
  syncConsole,
};
