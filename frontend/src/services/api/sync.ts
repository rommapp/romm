import type {
  ClientSaveState,
  DeviceCreatePayload,
  DeviceCreateResponse,
  SyncCompletePayload,
  SyncNegotiateResponse,
} from "@/__generated__";
import api from "@/services/api";

async function registerDevice(payload: DeviceCreatePayload) {
  return api.post<DeviceCreateResponse>("/devices", payload);
}

async function negotiate({
  deviceId,
  romIds,
  saves,
  restoreUnlisted = false,
}: {
  deviceId: string;
  romIds: number[];
  saves: ClientSaveState[];
  /** Offer server saves the client did not list, even ones it synced before. */
  restoreUnlisted?: boolean;
}) {
  return api.post<SyncNegotiateResponse>("/sync/negotiate", {
    device_id: deviceId,
    rom_ids: romIds,
    saves,
    restore_unlisted: restoreUnlisted,
  });
}

async function completeSession(
  sessionId: number,
  payload: SyncCompletePayload,
) {
  return api.post(`/sync/sessions/${sessionId}/complete`, payload);
}

/** A save's bytes, recorded against the device as the version it now holds. */
async function downloadSave({
  saveId,
  deviceId,
  sessionId,
}: {
  saveId: number;
  deviceId: string;
  sessionId: number;
}) {
  return api.get<ArrayBuffer>(`/saves/${saveId}/content`, {
    params: { device_id: deviceId, session_id: sessionId, optimistic: true },
    responseType: "arraybuffer",
  });
}

/** Confirm the device wrote a downloaded save, with its own hash of the bytes. */
async function confirmDownloaded({
  saveId,
  deviceId,
  contentHash,
}: {
  saveId: number;
  deviceId: string;
  contentHash: string;
}) {
  return api.post(`/saves/${saveId}/downloaded`, {
    device_id: deviceId,
    content_hash: contentHash,
  });
}

export default {
  registerDevice,
  negotiate,
  completeSession,
  downloadSave,
  confirmDownloaded,
};
