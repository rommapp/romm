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
}: {
  deviceId: string;
  romIds: number[];
  saves: ClientSaveState[];
}) {
  return api.post<SyncNegotiateResponse>("/sync/negotiate", {
    device_id: deviceId,
    rom_ids: romIds,
    saves,
    // A browser never deletes a save itself, so one it no longer holds was lost.
    restore_unlisted: true,
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
