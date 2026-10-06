import type {
  ChannelSchema,
  SaveFormat,
  SaveShape,
  SnapshotSchema,
} from "@/__generated__";
import api from "@/services/api";

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
  approve_hardcore_downgrade?: boolean;
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

/** A push whose content the server already holds, so it carries no file parts. */
async function pushSnapshot({ manifest }: { manifest: SnapshotManifest }) {
  const formData = new FormData();
  formData.append("manifest", JSON.stringify(manifest));
  return api.post<SnapshotSchema>("/snapshots", formData);
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
  pushSnapshot,
  setSnapshotPinned,
};
