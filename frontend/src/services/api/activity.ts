import api from "@/services/api";

export interface ActivityEntry {
  user_id: number;
  username: string;
  avatar_path: string;
  rom_id: number;
  rom_name: string;
  rom_cover_path: string;
  platform_slug: string;
  platform_name: string;
  device_id: string;
  device_type: string;
  started_at: string;
}

export interface ActivityClearEvent {
  user_id: number;
  device_id: string;
  rom_id: number;
}

async function getAllActivity() {
  return api.get<ActivityEntry[]>("/activity");
}

async function getRomActivity(romId: number) {
  return api.get<ActivityEntry[]>(`/activity/rom/${romId}`);
}

async function sendDeviceHeartbeat(romId: number, deviceId: string) {
  return api.post<ActivityEntry>("/activity/heartbeat", {
    rom_id: romId,
    device_id: deviceId,
  });
}

async function clearDeviceActivity(deviceId: string) {
  return api.delete("/activity/heartbeat", {
    params: { device_id: deviceId },
  });
}

export default {
  getAllActivity,
  getRomActivity,
  sendDeviceHeartbeat,
  clearDeviceActivity,
};
