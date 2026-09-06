import type {
  LaunchMode,
  ShortcutSchema,
  ShortcutStatus,
} from "@/__generated__";
import api from "@/services/api";

export type { ShortcutSchema, ShortcutStatus } from "@/__generated__";

async function fetchShortcuts({
  romId,
  deviceId,
  statuses,
}: {
  romId?: number;
  deviceId?: string;
  statuses?: ShortcutStatus[];
} = {}) {
  return api.get<ShortcutSchema[]>("/shortcuts", {
    params: {
      rom_id: romId,
      device_id: deviceId,
      status: statuses?.length ? statuses.join(",") : undefined,
    },
  });
}

async function addShortcut({
  romId,
  deviceId,
  launchMode,
}: {
  romId: number;
  deviceId: string;
  launchMode?: LaunchMode;
}) {
  return api.put<ShortcutSchema>("/shortcuts", {
    rom_id: romId,
    device_id: deviceId,
    launch_mode: launchMode ?? null,
  });
}

async function removeShortcut(shortcutId: number) {
  return api.delete<ShortcutSchema>(`/shortcuts/${shortcutId}`);
}

export default { fetchShortcuts, addShortcut, removeShortcut };
