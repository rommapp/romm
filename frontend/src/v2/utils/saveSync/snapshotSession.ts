import { isAxiosError } from "axios";
import type {
  ChannelSchema,
  SaveSchema,
  SnapshotConflictSchema,
  SnapshotSchema,
} from "@/__generated__";
import snapshotApi, {
  SAVE_PART,
  statePart,
  type Bank,
  type SnapshotManifest,
  type SnapshotPart,
} from "@/services/api/snapshot";
import { saveContentHash } from "@/v2/utils/saveSync/hash";
import { bankOf, channelLabelForSlot } from "@/v2/utils/snapshots";

/** Where a session's pushes land, and the snapshot they build on. */
export interface SnapshotTarget {
  romFileId: number;
  /** Null until the first push creates the channel named `label`. */
  channelId: string | null;
  label: string;
  expectedCurrentId: number | null;
  /** Null carries the expected current. */
  parentSnapshotId: number | null;
  /** The parent's bank, which a state push extends. */
  bank: Bank;
  /** The hash of the parent's save, so an unchanged SRAM is not sent again. */
  saveHash: string | null;
  core: string;
  emulatorVersion: string | null;
}

export interface SessionTargetInput {
  rom: {
    channel_file_id: number | null;
    user_channels: readonly ChannelSchema[];
  };
  core: string;
  emulatorVersion?: string | null | undefined;
  /** The snapshot the session booted, which pushes build on. */
  snapshot?: SnapshotSchema | null | undefined;
  /** The save the session booted, which ties it to that save's channel. */
  save?: Pick<SaveSchema, "channel_id"> | null | undefined;
  /** The slot the session files under when nothing booted names a channel. */
  slot: string;
}

function ownChannel(
  channels: readonly ChannelSchema[],
  match: (channel: ChannelSchema) => boolean,
): ChannelSchema | undefined {
  return channels.find((channel) => channel.is_own && match(channel));
}

/**
 * The channel a session writes to: the booted snapshot's, else the booted
 * save's, else the one its slot names on the ROM's channel file.
 *
 * Returns:
 *   Null when the ROM has no file a channel can key to.
 */
export function sessionTarget({
  rom,
  core,
  emulatorVersion = null,
  snapshot,
  save,
  slot,
}: SessionTargetInput): SnapshotTarget | null {
  const ran = { core, emulatorVersion };
  const booted = snapshot?.channel
    ? ownChannel(rom.user_channels, (c) => c.id === snapshot.channel?.id)
    : undefined;
  if (snapshot && booted?.rom_file_id != null) {
    return {
      ...ran,
      romFileId: booted.rom_file_id,
      channelId: booted.id,
      label: booted.label,
      expectedCurrentId: booted.current_snapshot_id,
      parentSnapshotId: snapshot.id,
      bank: bankOf(snapshot),
      saveHash: snapshot.save?.content_hash ?? null,
    };
  }

  const label = channelLabelForSlot(slot);
  const channel =
    (save?.channel_id
      ? ownChannel(rom.user_channels, (c) => c.id === save.channel_id)
      : undefined) ??
    ownChannel(
      rom.user_channels,
      (c) =>
        c.rom_file_id === rom.channel_file_id &&
        c.label.toLowerCase() === label.toLowerCase(),
    );
  const romFileId = channel?.rom_file_id ?? rom.channel_file_id;
  if (romFileId == null) return null;
  const current = channel?.current ?? null;
  return {
    ...ran,
    romFileId,
    channelId: channel?.id ?? null,
    label: channel?.label ?? label,
    expectedCurrentId: channel?.current_snapshot_id ?? null,
    parentSnapshotId: null,
    bank: current ? bankOf(current) : {},
    saveHash: current?.save?.content_hash ?? null,
  };
}

/** A file a session wrote, kept as bytes so a held push survives a reload. */
export interface SessionFile {
  bytes: ArrayBuffer;
  fileName: string;
  screenshot?: ArrayBuffer | undefined;
  screenshotName?: string | undefined;
}

/** A file a push sends, under its part key. */
export type PushFile = SessionFile & { key: string };

/** Everything one push sends, ready to send now or to hold for later. */
export interface SnapshotPush {
  manifest: SnapshotManifest;
  files: PushFile[];
  deviceId?: string | undefined;
}

export type SnapshotContent =
  | { kind: "save"; save: SessionFile }
  | {
      kind: "state";
      slot: string;
      state: SessionFile;
      /** The SRAM beside the state, sent when the parent holds another one. */
      save: SessionFile | null;
    };

export type PushOutcome =
  | { kind: "current"; snapshot: SnapshotSchema }
  | {
      kind: "branched";
      snapshot: SnapshotSchema;
      /** Another device moved the channel on, or its current is hardcore. */
      reason: "moved" | "hardcore";
    };

function pushFile(key: string, file: SessionFile): PushFile {
  return { key, ...file };
}

function partsOf(files: readonly PushFile[]): SnapshotPart[] {
  const type = "application/octet-stream";
  return files.map((file) => ({
    key: file.key,
    file: new File([file.bytes], file.fileName, { type }),
    screenshot:
      file.screenshot && file.screenshotName
        ? new File([file.screenshot], file.screenshotName, { type })
        : undefined,
  }));
}

/** Hashes by buffer, since holding a push and then sending it builds it twice. */
const hashes = new WeakMap<ArrayBuffer, string>();

function hashOf(file: SessionFile): string {
  let hash = hashes.get(file.bytes);
  if (hash === undefined) {
    hash = saveContentHash(new Uint8Array(file.bytes));
    hashes.set(file.bytes, hash);
  }
  return hash;
}

/** The push `content` makes on top of `target`. */
export function buildPush(
  target: SnapshotTarget,
  content: SnapshotContent,
  deviceId?: string,
): SnapshotPush {
  const manifest: SnapshotManifest = {
    rom_file_id: target.romFileId,
    expected_current_id: target.expectedCurrentId,
    ...(target.channelId ? { channel_id: target.channelId } : {}),
    label: target.label,
    ...(target.parentSnapshotId != null
      ? { parent_snapshot_id: target.parentSnapshotId }
      : {}),
    emulator: target.core,
    core: target.core,
    ...(target.emulatorVersion
      ? { emulator_version: target.emulatorVersion }
      : {}),
  };
  const files: PushFile[] = [];
  const { save } = content;
  if (save) {
    const hash = hashOf(save);
    if (content.kind === "save" || hash !== target.saveHash) {
      manifest.save = { hash, shape: "SINGLE", format: "native" };
      files.push(pushFile(SAVE_PART, save));
    }
  }
  if (content.kind === "state") {
    manifest.states = {
      [target.core]: {
        ...(target.bank[target.core] ?? {}),
        [content.slot]: hashOf(content.state),
      },
    };
    files.push(pushFile(statePart(target.core, content.slot), content.state));
  }
  return { manifest, files, deviceId };
}

function conflictOf(error: unknown): SnapshotConflictSchema | null {
  if (!isAxiosError(error) || error.response?.status !== 409) return null;
  const body = error.response.data as Partial<SnapshotConflictSchema> | null;
  return body?.branch ? (body as SnapshotConflictSchema) : null;
}

const PARENT_GONE = "Parent snapshot not found";

/** Whether the server refused a softcore push onto a hardcore current. */
export function isHardcoreRefusal(error: unknown): boolean {
  if (!isAxiosError(error) || error.response?.status !== 409) return false;
  const body = error.response.data as { hardcore_downgrade?: unknown } | null;
  return body?.hardcore_downgrade === true;
}

function withoutMissing(states: Bank, missing: ReadonlySet<string>): Bank {
  return Object.fromEntries(
    Object.entries(states).map(([core, slots]) => [
      core,
      Object.fromEntries(
        Object.entries(slots).filter(
          ([slot]) => !missing.has(statePart(core, slot)),
        ),
      ),
    ]),
  );
}

/**
 * The push to retry with when retention removed what this one builds on or a
 * hardcore current refused it; null when the refusal is final.
 */
export function fallbackPush(
  push: SnapshotPush,
  error: unknown,
): SnapshotPush | null {
  if (!isAxiosError(error)) return null;
  const status = error.response?.status;
  const body = error.response?.data as
    { detail?: unknown; missing?: unknown } | undefined;
  if (isHardcoreRefusal(error)) {
    const { manifest } = push;
    if (manifest.expected_current_id === null) return null;
    return {
      ...push,
      manifest: {
        ...manifest,
        expected_current_id: null,
        parent_snapshot_id:
          manifest.parent_snapshot_id ?? manifest.expected_current_id,
      },
    };
  }
  if (status === 404 && body?.detail === PARENT_GONE) {
    const { parent_snapshot_id, ...manifest } = push.manifest;
    if (parent_snapshot_id !== undefined) return { ...push, manifest };
    if (manifest.expected_current_id === null) return null;
    return { ...push, manifest: { ...manifest, expected_current_id: null } };
  }
  if (status === 400 && Array.isArray(body?.missing)) {
    const missing = new Set(body.missing as string[]);
    if (push.files.some((file) => missing.has(file.key))) return null;
    const { states } = push.manifest;
    return {
      ...push,
      manifest: {
        ...push.manifest,
        ...(states ? { states: withoutMissing(states, missing) } : {}),
        ...(missing.has(SAVE_PART) ? { save: null } : {}),
      },
    };
  }
  return null;
}

const MAX_FALLBACKS = 3;

/**
 * Sends a push, kept as a branch when another device moved the channel on and
 * resent without whatever retention removed from under it.
 *
 * Raises:
 *   The request's error for any other refusal or failure.
 */
export async function sendPush(push: SnapshotPush): Promise<PushOutcome> {
  let attempt = push;
  let reason: "moved" | "hardcore" = "moved";
  for (let fallbacks = 0; ; fallbacks++) {
    try {
      const { data } = await snapshotApi.pushSnapshot({
        manifest: attempt.manifest,
        parts: partsOf(attempt.files),
        deviceId: attempt.deviceId,
      });
      return { kind: "current", snapshot: data };
    } catch (error) {
      const conflict = conflictOf(error);
      if (conflict) {
        return { kind: "branched", snapshot: conflict.branch, reason };
      }
      const next =
        fallbacks < MAX_FALLBACKS ? fallbackPush(attempt, error) : null;
      if (!next) throw error;
      if (isHardcoreRefusal(error)) reason = "hardcore";
      attempt = next;
    }
  }
}

/** `sendPush` while the page unloads; false when it is too big to go. */
export function sendPushOnUnload(push: SnapshotPush): boolean {
  return snapshotApi.sendSnapshotOnUnload({
    manifest: push.manifest,
    parts: partsOf(push.files),
    deviceId: push.deviceId,
  });
}

/**
 * One play session's writes into a channel, sent in order so each builds on
 * the last. Once another device moves the channel on, they chain as a branch.
 */
export class SnapshotSession {
  private target: SnapshotTarget;
  private readonly deviceId: string | undefined;
  private queue: Promise<unknown> = Promise.resolve();

  constructor(target: SnapshotTarget, deviceId?: string) {
    this.target = target;
    this.deviceId = deviceId;
  }

  /** The push `content` would make now, to hold before it is sent. */
  build(content: SnapshotContent): SnapshotPush {
    return buildPush(this.target, content, this.deviceId);
  }

  /** Sends `content` once the pushes before it are done. */
  push(content: SnapshotContent): Promise<PushOutcome> {
    const run = this.queue.then(async () => {
      const outcome = await sendPush(this.build(content));
      this.advance(outcome);
      return outcome;
    });
    this.queue = run.catch(() => undefined);
    return run;
  }

  private advance({ kind, snapshot }: PushOutcome) {
    const next: SnapshotTarget = {
      ...this.target,
      channelId: snapshot.channel?.id ?? this.target.channelId,
      bank: bankOf(snapshot),
      saveHash: snapshot.save?.content_hash ?? null,
    };
    if (kind === "branched") {
      next.parentSnapshotId = snapshot.id;
    } else {
      next.expectedCurrentId = snapshot.id;
      next.parentSnapshotId = null;
    }
    this.target = next;
  }
}
