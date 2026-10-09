import type {
  ChannelSchema,
  SaveFormat,
  SaveShape,
  SnapshotSchema,
} from "@/__generated__";
import api, { keepaliveFormHeaders } from "@/services/api";
import { UNLOAD_SAVE_MAX_BYTES } from "@/services/api/save";

/** The backend's `CHANNEL_LABEL_MAX_LENGTH`, so the field stops at the limit. */
export const CHANNEL_LABEL_MAX_LENGTH = 255;

/** A bank: core → slot → content hash. */
export type Bank = Record<string, Record<string, string>>;

/** The save a push names, by hash or by a save of the caller's to copy in. */
export type ManifestSave =
  | { hash: string; shape: SaveShape; format: SaveFormat }
  | { copy_of: number; shape?: SaveShape; format?: SaveFormat };

/**
 * What a push declares. Leaving `save` out carries the parent's save; a core
 * listed in `states` replaces the parent's, so a slot left out of it goes.
 */
export interface SnapshotManifest {
  rom_file_id: number;
  expected_current_id: number | null;
  channel_id?: string;
  label?: string;
  parent_snapshot_id?: number;
  save?: ManifestSave | null;
  states?: Bank;
  is_hardcore?: boolean;
  approve_hardcore_downgrade?: boolean;
  emulator?: string;
  emulator_version?: string;
  core?: string;
}

/** A file a push carries, under the part name the manifest's hash maps to. */
export interface SnapshotPart {
  /** `save`, or `state:<core>:<slot>`. */
  key: string;
  file: File;
  screenshot?: File | undefined;
}

export const SAVE_PART = "save";

export function statePart(core: string, slot: string): string {
  return `state:${core}:${slot}`;
}

function screenshotPart(key: string): string {
  return key === SAVE_PART ? "save_screenshot" : `${key}:screenshot`;
}

function pushFormData(
  manifest: SnapshotManifest,
  parts: readonly SnapshotPart[],
): FormData {
  const formData = new FormData();
  formData.append("manifest", JSON.stringify(manifest));
  for (const part of parts) {
    formData.append(part.key, part.file);
    if (part.screenshot)
      formData.append(screenshotPart(part.key), part.screenshot);
  }
  return formData;
}

async function createChannel({
  romFileId,
  label,
}: {
  romFileId: number;
  label: string;
}) {
  return api.post<ChannelSchema>("/channels", {
    rom_file_id: romFileId,
    label,
  });
}

async function updateChannel({
  id,
  label,
  isPublic,
}: {
  id: string;
  label?: string;
  isPublic?: boolean;
}) {
  return api.patch<ChannelSchema>(`/channels/${id}`, {
    label,
    is_public: isPublic,
  });
}

async function deleteChannel({ id }: { id: string }) {
  return api.delete<void>(`/channels/${id}`);
}

/** The caller's channels on a platform whose ROM was removed. */
async function getDetachedChannels({ platformId }: { platformId: number }) {
  return api.get<ChannelSchema[]>("/channels", {
    params: { detached_platform_id: platformId },
  });
}

async function attachChannel({
  id,
  romFileId,
}: {
  id: string;
  romFileId: number;
}) {
  return api.post<ChannelSchema>(`/channels/${id}/attach`, {
    rom_file_id: romFileId,
  });
}

async function getChannelHistory({
  channelId,
  limit,
  cursor,
}: {
  channelId: string;
  limit?: number;
  cursor?: number | undefined;
}) {
  return api.get<SnapshotSchema[]>("/snapshots", {
    params: { channel_id: channelId, limit, cursor },
  });
}

async function getSnapshot({ id }: { id: number }) {
  return api.get<SnapshotSchema>(`/snapshots/${id}`);
}

/**
 * Writes a snapshot, sending `parts` only for hashes the server lacks. A 409
 * carries a `SnapshotConflictSchema` when the push was kept as a branch.
 */
async function pushSnapshot({
  manifest,
  parts = [],
  deviceId,
}: {
  manifest: SnapshotManifest;
  parts?: readonly SnapshotPart[];
  deviceId?: string | undefined;
}) {
  return api.post<SnapshotSchema>("/snapshots", pushFormData(manifest, parts), {
    params: { device_id: deviceId },
  });
}

/**
 * `pushSnapshot` while the page unloads, which nothing outlives to await.
 *
 * Returns:
 *   False when the files are too big for a keepalive body.
 */
function sendSnapshotOnUnload({
  manifest,
  parts,
  deviceId,
}: {
  manifest: SnapshotManifest;
  parts: readonly SnapshotPart[];
  deviceId?: string | undefined;
}): boolean {
  const size = parts.reduce(
    (total, part) => total + part.file.size + (part.screenshot?.size ?? 0),
    0,
  );
  if (size > UNLOAD_SAVE_MAX_BYTES) return false;
  void fetch(
    api.getUri({ url: "/snapshots", params: { device_id: deviceId } }),
    {
      method: "POST",
      body: pushFormData(manifest, parts),
      keepalive: true,
      credentials: "same-origin",
      headers: keepaliveFormHeaders(),
    },
  ).catch(() => undefined);
  return true;
}

async function setSnapshotPinned({
  id,
  isPinned,
}: {
  id: number;
  isPinned: boolean;
}) {
  return api.patch<SnapshotSchema>(`/snapshots/${id}`, { is_pinned: isPinned });
}

export default {
  createChannel,
  updateChannel,
  deleteChannel,
  getDetachedChannels,
  attachChannel,
  getChannelHistory,
  getSnapshot,
  pushSnapshot,
  sendSnapshotOnUnload,
  setSnapshotPinned,
};
