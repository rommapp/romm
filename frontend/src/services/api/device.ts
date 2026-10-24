import type {
  DeviceSchema,
  DeviceUpdatePayload,
  PS3ConsoleCreatePayload,
  PS3ConsoleUpdatePayload,
  PS3ProbePayload,
  PS3ProbeResponse,
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

async function addPS3(payload: PS3ConsoleCreatePayload) {
  return api.post<DeviceSchema>("/devices/consoles/ps3", payload);
}

async function updatePS3(id: string, payload: PS3ConsoleUpdatePayload) {
  return api.put<DeviceSchema>(
    `/devices/consoles/ps3/${encodeURIComponent(id)}`,
    payload,
  );
}

async function probePS3(payload: PS3ProbePayload) {
  return api.post<PS3ProbeResponse>("/devices/consoles/ps3/probe", payload);
}

async function syncPS3(id: string) {
  return api.post<SyncSessionSchema>(
    `/devices/consoles/ps3/${encodeURIComponent(id)}/sync`,
  );
}

export default {
  fetchDevices,
  fetchOnlineDeviceIds,
  updateDevice,
  deleteDevice,
  addPS3,
  updatePS3,
  probePS3,
  syncPS3,
};
