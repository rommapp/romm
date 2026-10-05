import type { DeviceSchema, DeviceUpdatePayload } from "@/__generated__";
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

export default {
  fetchDevices,
  fetchOnlineDeviceIds,
  updateDevice,
  deleteDevice,
};
