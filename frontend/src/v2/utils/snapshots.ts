import type {
  ChannelSchema,
  SaveSchema,
  SnapshotSchema,
} from "@/__generated__";
import type { Bank, SnapshotManifest } from "@/services/api/snapshot";

/** A save or state no channel holds, which the user manages freely. */
export function isBackup(asset: { channel_id?: string | null }): boolean {
  return !asset.channel_id;
}

/** The parts of a channel a push into it needs. */
type ChannelTarget = Pick<
  ChannelSchema,
  "id" | "rom_file_id" | "current_snapshot_id"
>;

/** A snapshot's bank as the hashes a manifest names. */
export function bankOf(snapshot: SnapshotSchema): Bank {
  return Object.fromEntries(
    Object.entries(snapshot.states).map(([core, slots]) => [
      core,
      Object.fromEntries(
        Object.entries(slots).map(([slot, state]) => [
          slot,
          state.content_hash ?? "",
        ]),
      ),
    ]),
  );
}

function intoChannel(
  channel: ChannelTarget,
  rest: Partial<SnapshotManifest>,
): SnapshotManifest | null {
  if (channel.rom_file_id == null) return null;
  return {
    rom_file_id: channel.rom_file_id,
    channel_id: channel.id,
    expected_current_id: channel.current_snapshot_id,
    ...rest,
  };
}

/**
 * Makes `snapshot` the channel's current again, as a new snapshot on top of
 * what is there now, so history is never rewritten. Like every builder here,
 * it names only hashes the server holds, so no file travels.
 */
export function restoreManifest(
  snapshot: SnapshotSchema,
  channel: ChannelTarget,
): SnapshotManifest | null {
  return intoChannel(channel, { parent_snapshot_id: snapshot.id });
}

/** `snapshot` without one bank slot, pushed as the channel's new current. */
export function withoutStateManifest(
  snapshot: SnapshotSchema,
  channel: ChannelTarget,
  core: string,
  slot: string,
): SnapshotManifest | null {
  const slots = { ...(bankOf(snapshot)[core] ?? {}) };
  delete slots[slot];
  return intoChannel(channel, {
    parent_snapshot_id: snapshot.id,
    states: { [core]: slots },
  });
}

/** `snapshot` copied on top of another channel on the same file. */
export function copyOverManifest(
  snapshot: SnapshotSchema,
  target: ChannelTarget,
): SnapshotManifest | null {
  return intoChannel(target, { parent_snapshot_id: snapshot.id });
}

/** A new channel that starts from `snapshot`. */
export function forkManifest(
  snapshot: SnapshotSchema,
  romFileId: number,
  label: string,
): SnapshotManifest {
  return {
    rom_file_id: romFileId,
    label,
    expected_current_id: null,
    parent_snapshot_id: snapshot.id,
  };
}

/** A save outside any snapshot (a backup or an older client's), copied in as
 *  the channel's new current. The server copies the file, so the original
 *  stays as it is. */
export function copySaveManifest(
  save: Pick<SaveSchema, "id">,
  channel: ChannelTarget,
): SnapshotManifest | null {
  return intoChannel(channel, { save: { copy_of: save.id } });
}

/** Channels a snapshot can be copied over: the user's own on the same file. */
export function copyTargets(
  channels: ChannelSchema[],
  from: Pick<ChannelSchema, "id" | "rom_file_id">,
): ChannelSchema[] {
  return channels.filter(
    (c) =>
      c.is_own &&
      c.id !== from.id &&
      c.rom_file_id != null &&
      c.rom_file_id === from.rom_file_id,
  );
}
