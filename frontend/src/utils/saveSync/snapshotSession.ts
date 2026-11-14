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
import { saveContentHash } from "@/utils/saveSync/hash";
import { bankOf, channelLabelForSlot, ownChannel } from "@/utils/snapshots";
import { uuidv7 } from "@/utils/uuid";

/** Where a session's pushes land, and the snapshot they build on. */
export interface SnapshotTarget {
  romFileId: number;
  /** For a new channel, the id its first push creates it under. */
  channelId: string;
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

interface SessionTargetInput {
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
  const booted = ownChannel(rom.user_channels, snapshot?.channel_id);
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

  const slotLabel = channelLabelForSlot(slot);
  const channel =
    ownChannel(rom.user_channels, save?.channel_id) ??
    rom.user_channels.find(
      (c) =>
        c.is_own &&
        c.rom_file_id === rom.channel_file_id &&
        c.label.toLowerCase() === slotLabel?.toLowerCase(),
    );
  const label = channel?.label ?? slotLabel;
  const romFileId = channel?.rom_file_id ?? rom.channel_file_id;
  // A slot that files under no channel, as legacy uploads treat it, gets no session.
  if (romFileId == null || label === null) return null;
  const current = channel?.current ?? null;
  return {
    ...ran,
    romFileId,
    channelId: channel?.id ?? uuidv7(),
    label,
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
type PushFile = SessionFile & { key: string };

/** Everything one push sends. */
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

function requestOf(push: SnapshotPush) {
  return {
    manifest: push.manifest,
    parts: partsOf(push.files),
    deviceId: push.deviceId,
  };
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

function hashOf(file: SessionFile): string {
  return saveContentHash(new Uint8Array(file.bytes));
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
    channel_id: target.channelId,
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
      files.push({ key: SAVE_PART, ...save });
    }
  }
  if (content.kind === "state") {
    manifest.states = {
      [target.core]: {
        ...(target.bank[target.core] ?? {}),
        [content.slot]: hashOf(content.state),
      },
    };
    files.push({ key: statePart(target.core, content.slot), ...content.state });
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
      const { data } = await snapshotApi.pushSnapshot(requestOf(attempt));
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
  return snapshotApi.sendSnapshotOnUnload(requestOf(push));
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

  /** The push `content` would make now. */
  build(content: SnapshotContent): SnapshotPush {
    return buildPush(this.target, content, this.deviceId);
  }

  /** `content` with the base it is written on, to keep until the server takes it. */
  hold(content: SnapshotContent): HeldPush {
    return { target: this.target, content, deviceId: this.deviceId };
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
      channelId: snapshot.channel_id ?? this.target.channelId,
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

/** A write the server has not taken, with the base its session had then. */
export interface HeldPush {
  target: SnapshotTarget;
  content: SnapshotContent;
  deviceId?: string | undefined;
}

function sameBase(a: SnapshotTarget, b: SnapshotTarget): boolean {
  return (
    a.channelId === b.channelId &&
    a.expectedCurrentId === b.expectedCurrentId &&
    a.parentSnapshotId === b.parentSnapshotId
  );
}

/**
 * Sends held pushes oldest first. Ones held on the same base go through one
 * session, so they chain like a live session's instead of branching.
 */
export function heldPushSender(): (held: HeldPush) => Promise<PushOutcome> {
  const sessions = new Map<
    string,
    { base: SnapshotTarget; session: SnapshotSession }
  >();
  return (held) => {
    const { target } = held;
    const last = sessions.get(target.channelId);
    const session =
      last && sameBase(last.base, target)
        ? last.session
        : new SnapshotSession(target, held.deviceId);
    sessions.set(target.channelId, { base: target, session });
    return session.push(held.content);
  };
}
