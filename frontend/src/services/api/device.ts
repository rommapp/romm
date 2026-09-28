import type { DeviceSchema } from "@/__generated__";
import api from "@/services/api";

async function fetchDevices() {
  return api.get<DeviceSchema[]>("/devices");
}

async function fetchOnlineDeviceIds() {
  return api.get<string[]>("/devices/online");
}

export default {
  fetchDevices,
  fetchOnlineDeviceIds,
};
