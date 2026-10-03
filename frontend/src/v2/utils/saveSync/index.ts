import { isAxiosError } from "axios";
import type { SyncOperationSchema } from "@/__generated__";
import saveApi from "@/services/api/save";
import syncApi from "@/services/api/sync";
import { isSlotConflict, uploadArchivedSave } from "@/services/pending-asset";
import { browserDeviceId } from "./browserDevice";
import { bytesEqual, saveContentHash } from "./hash";
import {
  deleteLocalSave,
  listLocalSaves,
  putLocalSave,
  type LocalSave,
} from "./localSaves";

export type { LocalSave } from "./localSaves";

/** How often a player whose storage cannot signal a write is polled for saves. */
export const PLAYER_SAVE_POLL_MS = 5000;

export interface SaveSyncRom {
  id: number;
  fs_name_no_ext: string;
}

/** A save as a player holds it, before it becomes this browser's copy. */
export interface PlayerSaveFile {
  slot: string;
  fileName: string;
  bytes: Uint8Array;
  updatedAt: number;
}

function saveFileOf(save: LocalSave): File {
  return new File([save.bytes as BlobPart], save.fileName, {
    type: "application/octet-stream",
  });
}

function extensionOf(fileName: string): string {
  const dot = fileName.lastIndexOf(".");
  return dot > 0 ? fileName.slice(dot) : "";
}

function statusOf(error: unknown): number | undefined {
  return isAxiosError(error) ? error.response?.status : undefined;
}

/**
 * Keeps one game's saves in this browser in step with the server, as a sync
 * device: negotiated at launch, then pushed as the player writes them.
 */
export class DeviceSaveSync {
  private readonly rom: SaveSyncRom;
  private readonly userId: number;
  private readonly emulator: string;
  private readonly saves = new Map<string, LocalSave>();
  // Null until a negotiation succeeds; the saves then stay in this browser.
  private deviceId: string | null = null;
  // Pushes run one after another, so two never upload the same change.
  private pushQueue: Promise<unknown> = Promise.resolve();

  constructor(rom: SaveSyncRom, userId: number, emulator: string) {
    this.rom = rom;
    this.userId = userId;
    this.emulator = emulator;
  }

  /**
   * Sync before a launch, folding in what the player already holds.
   *
   * Args:
   *   existing: Saves found in the player's own storage, kept when newer.
   *
   * Returns:
   *   The saves to hand the player, synced or, when offline, as held here.
   */
  async prepare(existing: PlayerSaveFile[] = []): Promise<LocalSave[]> {
    for (const save of await listLocalSaves(this.userId, this.rom.id)) {
      this.saves.set(save.slot, save);
    }
    await this.capture(existing);
    try {
      await this.negotiate();
    } catch (error) {
      console.error("[Save sync] Negotiation failed", error);
    }
    return [...this.saves.values()];
  }

  /** Keep what the player wrote, for the next push. */
  async capture(files: PlayerSaveFile[]): Promise<void> {
    await Promise.all(this.track(files).map((save) => putLocalSave(save)));
  }

  /** Capture and send what the player wrote while the page goes away. */
  captureOnUnload(files: PlayerSaveFile[]): void {
    const changed = this.track(files);
    // Sent first: a closing page may not live to finish an IndexedDB write.
    this.pushOnUnload();
    for (const save of changed) void putLocalSave(save).catch(() => undefined);
  }

  /**
   * Upload every save that changed since the server last held it.
   *
   * Returns:
   *   False when one failed to upload; it is retried on the next push.
   */
  push(): Promise<boolean> {
    const run = this.pushQueue.then(() => this.uploadChanged());
    this.pushQueue = run;
    return run;
  }

  private async uploadChanged(): Promise<boolean> {
    if (!this.deviceId) return true;
    try {
      await Promise.all(
        this.changed().map((save) => this.upload(save, { overwrite: false })),
      );
      return true;
    } catch (error) {
      console.error("[Save sync] Upload failed", error);
      return false;
    }
  }

  /** Send the changed saves while the page goes away. */
  pushOnUnload(): void {
    if (!this.deviceId) return;
    for (const save of this.changed()) {
      saveApi.sendSaveOnUnload({
        rom: this.rom,
        emulator: save.emulator,
        deviceId: this.deviceId,
        slot: save.slot,
        contentHash: save.hash,
        autocleanup: true,
        // A refused copy stays in this browser for the next launch to settle.
        overwrite: false,
        save: null,
        saveFile: saveFileOf(save),
      });
    }
  }

  // Takes the changed files in memory at once, returning them for storing.
  private track(files: PlayerSaveFile[]): LocalSave[] {
    const changed: LocalSave[] = [];
    for (const file of files) {
      const held = this.saves.get(file.slot);
      if (held && bytesEqual(held.bytes, file.bytes)) continue;
      const hash = saveContentHash(file.bytes);
      if (held?.hash === hash) continue;
      const save: LocalSave = {
        userId: this.userId,
        romId: this.rom.id,
        slot: file.slot,
        fileName: file.fileName,
        emulator: this.emulator,
        bytes: file.bytes,
        updatedAt: file.updatedAt,
        hash,
        syncedHash: held?.syncedHash ?? null,
      };
      this.saves.set(save.slot, save);
      changed.push(save);
    }
    return changed;
  }

  private changed(): LocalSave[] {
    return [...this.saves.values()].filter(
      (save) => save.hash !== save.syncedHash,
    );
  }

  // Held in memory before the store write, so a capture landing meanwhile
  // builds on this copy instead of being overwritten by it.
  private async remember(save: LocalSave) {
    this.saves.set(save.slot, save);
    await putLocalSave(save);
  }

  private async negotiate() {
    let deviceId = await browserDeviceId(this.userId);
    if (!deviceId) return;
    const request = (id: string) =>
      syncApi.negotiate({
        deviceId: id,
        romIds: [this.rom.id],
        // A browser never deletes a save itself, so one it no longer holds was lost.
        restoreUnlisted: true,
        saves: [...this.saves.values()].map((save) => ({
          rom_id: save.romId,
          file_name: save.fileName,
          slot: save.slot,
          emulator: save.emulator,
          content_hash: save.hash,
          updated_at: new Date(save.updatedAt).toISOString(),
          file_size_bytes: save.bytes.byteLength,
        })),
      });

    let response;
    try {
      response = await request(deviceId);
    } catch (error) {
      // Sync turned off for this browser keeps its saves here.
      if (statusOf(error) === 400) return;
      if (statusOf(error) !== 404) throw error;
      // The device was removed, so this browser registers again.
      deviceId = await browserDeviceId(this.userId, { refresh: true });
      if (!deviceId) return;
      response = await request(deviceId);
    }
    this.deviceId = deviceId;

    const { session_id: sessionId, operations } = response.data;
    let completed = 0;
    let failed = 0;
    for (const operation of operations) {
      if (operation.rom_id !== this.rom.id || !operation.slot) continue;
      try {
        await this.apply(operation, operation.slot, sessionId);
        completed += 1;
      } catch (error) {
        failed += 1;
        console.error(`[Save sync] ${operation.action} failed`, error);
      }
    }
    void syncApi
      .completeSession(sessionId, {
        operations_completed: completed,
        operations_failed: failed,
      })
      .catch(() => undefined);
  }

  private async apply(
    operation: SyncOperationSchema,
    slot: string,
    sessionId: number,
  ) {
    const held = this.saves.get(slot);
    switch (operation.action) {
      case "upload":
        if (held) await this.upload(held, { overwrite: true, sessionId });
        return;
      case "download":
        await this.download(operation, slot, sessionId);
        return;
      case "conflict":
        // Both sides changed: the server's copy is played, this one archived.
        if (held) await this.archive(held);
        await this.download(operation, slot, sessionId);
        return;
      case "delete":
        await deleteLocalSave(this.userId, this.rom.id, slot);
        this.saves.delete(slot);
        return;
      case "no_op":
        // A no-op on differing bytes (clock skew, an untracked save) leaves
        // the change unsynced, for the next push.
        if (
          held &&
          held.syncedHash !== held.hash &&
          operation.server_content_hash === held.hash
        )
          await this.markSynced(held);
    }
  }

  private async download(
    operation: SyncOperationSchema,
    slot: string,
    sessionId: number,
  ) {
    const saveId = operation.save_id;
    const deviceId = this.deviceId;
    if (saveId == null || !deviceId) return;
    const { data } = await syncApi.downloadSave({
      saveId,
      deviceId,
      sessionId,
    });
    const bytes = new Uint8Array(data);
    const hash = saveContentHash(bytes);
    await this.remember({
      userId: this.userId,
      romId: this.rom.id,
      slot,
      fileName: operation.file_name,
      emulator: operation.emulator ?? this.emulator,
      bytes,
      updatedAt: Date.parse(operation.server_updated_at ?? "") || Date.now(),
      hash,
      syncedHash: hash,
    });
    await syncApi
      .confirmDownloaded({ saveId, deviceId, contentHash: hash })
      .catch((error: unknown) => {
        console.error("[Save sync] Download confirmation failed", error);
      });
  }

  private async upload(
    save: LocalSave,
    { overwrite, sessionId }: { overwrite: boolean; sessionId?: number },
  ) {
    const [result] = await saveApi.uploadSaves({
      rom: this.rom,
      emulator: save.emulator,
      deviceId: this.deviceId ?? undefined,
      slot: save.slot,
      contentHash: save.hash,
      sessionId,
      overwrite,
      autocleanup: true,
      savesToUpload: [{ saveFile: saveFileOf(save) }],
    });
    // Another device wrote the slot since this one last synced; keep this
    // copy as an archive and let the next launch settle the slot.
    if (isSlotConflict(result)) await this.archive(save);
    else if (result?.status !== "fulfilled") throw result?.reason;
    await this.markSynced(save);
  }

  // A newer capture may have landed while `save` uploaded, so only the hash
  // the server now holds is recorded against it.
  private async markSynced(save: LocalSave) {
    const current = this.saves.get(save.slot) ?? save;
    await this.remember({ ...current, syncedHash: save.hash });
  }

  private async archive(save: LocalSave) {
    const result = await uploadArchivedSave({
      rom: this.rom,
      emulator: save.emulator,
      deviceId: this.deviceId ?? undefined,
      capturedAt: new Date(save.updatedAt),
      bytes: save.bytes,
      extension: extensionOf(save.fileName),
    });
    if (result?.status !== "fulfilled") throw result?.reason;
  }
}
