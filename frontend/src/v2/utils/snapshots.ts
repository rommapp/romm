import type {
  ChannelSchema,
  SaveSchema,
  SnapshotSchema,
} from "@/__generated__";
import { AUTOSAVE_SLOT } from "@/services/api/save";
import type { Bank, SnapshotManifest } from "@/services/api/snapshot";
import type { CardBadge } from "@/v2/components/GameDetails/SaveChannels/SnapshotCard.vue";

/** The backend's `DEFAULT_CHANNEL_LABEL`. */
export const DEFAULT_CHANNEL_LABEL = "default";

/** The backend's `legacy.DEFAULT_SLOTS`. */
const DEFAULT_SLOTS = new Set([AUTOSAVE_SLOT, "default"]);

/** The backend's `utils.uploads.DATETIME_TAG_PATTERN`. */
const DATETIME_TAG_PATTERN =
  / \[\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}(?:-\d{3})?\]/g;

/** The channel a save slot files into, as the backend's `channel_label` maps it. */
export function channelLabelForSlot(slot: string): string {
  const label = slot.replace(DATETIME_TAG_PATTERN, "").trim();
  return !label || DEFAULT_SLOTS.has(label.toLowerCase())
    ? DEFAULT_CHANNEL_LABEL
    : label;
}

/** The state slot a snapshot client boots from by default. */
export const AUTO_STATE_SLOT = "auto";

/** RetroArch's default slot, where a client with a single manual slot files its captures. */
export const MANUAL_STATE_SLOT = "0";

/** The labels of the user's own channels, by id. */
export function ownChannelLabels(
  channels: readonly Pick<ChannelSchema, "id" | "label" | "is_own">[],
): Record<string, string> {
  return Object.fromEntries(
    channels.filter((c) => c.is_own).map((c) => [c.id, c.label]),
  );
}

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

/** A manifest that builds on `snapshot` keeps it hardcore when it was. */
function hardcoreOf(snapshot: SnapshotSchema): Partial<SnapshotManifest> {
  return snapshot.is_hardcore ? { is_hardcore: true } : {};
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
 * Makes `snapshot` the current of `channel` (its own or another on the same
 * file) as a new snapshot on top. It names only held hashes, so no file travels.
 */
export function restoreManifest(
  snapshot: SnapshotSchema,
  channel: ChannelTarget,
): SnapshotManifest | null {
  return intoChannel(channel, {
    parent_snapshot_id: snapshot.id,
    ...hardcoreOf(snapshot),
  });
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
    ...hardcoreOf(snapshot),
  });
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
    ...hardcoreOf(snapshot),
  };
}

/** A save outside any snapshot, copied in as the channel's new current; the original stays as it is. */
export function copySaveManifest(
  save: Pick<SaveSchema, "id">,
  channel: ChannelTarget,
): SnapshotManifest | null {
  return intoChannel(channel, { save: { copy_of: save.id } });
}

/** The badges a snapshot carries wherever it is listed or opened. */
export function snapshotBadges(
  snapshot: SnapshotSchema,
  channel: Pick<ChannelSchema, "current_snapshot_id">,
  t: (key: string) => string,
): CardBadge[] {
  const badges: CardBadge[] = [];
  if (snapshot.id === channel.current_snapshot_id) {
    badges.push({ label: t("channels.current"), color: "primary" });
  }
  if (snapshot.kind === "branch") {
    badges.push({ label: t("channels.branch"), outlined: true });
  }
  if (snapshot.pin_count > 0) {
    badges.push({ label: t("channels.pinned"), color: "accent" });
  }
  if (snapshot.is_hardcore) {
    badges.push({ label: t("channels.hardcore"), color: "warning" });
  }
  return badges;
}

/** Saves-tab items: backups and channels, not the rows channels hold. */
export function saveDataCounts({
  saves,
  states,
  channels,
}: {
  saves: readonly { channel_id?: string | null }[];
  states: readonly { channel_id?: string | null }[];
  channels: readonly ChannelSchema[];
}): { saves: number; states: number } {
  return {
    saves: saves.filter(isBackup).length + channels.length,
    states: states.filter(isBackup).length,
  };
}

/** Channels a snapshot can be saved over: the user's own on the same file. */
export function saveOverTargets(
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
