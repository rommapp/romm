import type { DeviceSchema } from "@/__generated__";
import api from "@/services/api";

async function fetchDevices() {
  return api.get<DeviceSchema[]>("/devices");
}

export default { fetchDevices };
