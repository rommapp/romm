// Saves and states the server has not accepted yet, held in the browser with
// the frame captured at the moment the game wrote them. A sync that fails
// offline would otherwise lose that frame and picture a later moment on the
// retry, and a closed tab would lose the progress outright.
import axios from "axios";
import type { DetailedRomSchema } from "@/__generated__";
import { isCsrfFailure } from "@/services/api";
import romApi from "@/services/api/rom";
import saveApi, { AUTOSAVE_SLOT, sessionSaveFile } from "@/services/api/save";
import stateApi, { sessionStateName } from "@/services/api/state";
import storeAuth from "@/stores/auth";

const DB_NAME = "romm-player";
// A row cannot be rekeyed or reshaped in place, so every upgrade rebuilds the
// store rather than migrating it.
const DB_VERSION = 4;
const STORE_NAME = "pending-assets";

export type PendingAssetKind = "save" | "state";

export interface PendingAsset {
  /** One row per capture, so two offline sessions cannot overwrite each other. */
  id: string;
  kind: PendingAssetKind;
  /** The account that captured it, stamped on write. */
  userId?: number | null;
  romId: number;
  /** Named at capture time, so a rom the server no longer has can still be announced. */
  romName: string;
  bytes: ArrayBuffer;
  screenshotBytes?: ArrayBuffer;
  /** Saves only: the slot the session was writing to. */
  slot?: string;
  emulator?: string;
  /** Saves only: the device the session was playing on. */
  deviceId?: string;
  capturedAt: number;
}

// `crypto.randomUUID` needs a secure context and RomM is often served over
// plain http on a LAN address. The id only has to be unique within a browser.
function randomToken(): string {
  const webCrypto = globalThis.crypto;
  if (typeof webCrypto?.randomUUID === "function")
    return webCrypto.randomUUID();
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

/** A key of its own for one capture, so no other can write over it. */
export function pendingAssetId(romId: number): string {
  return `${romId}:${randomToken()}`;
}

export interface PendingAssetStore {
  list(): Promise<PendingAsset[]>;
  write(entry: PendingAsset): Promise<void>;
  clear(id: string): Promise<void>;
}

function openDatabase(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);
    let abandoned = false;
    request.onupgradeneeded = () => {
      const db = request.result;
      for (const name of Array.from(db.objectStoreNames)) {
        db.deleteObjectStore(name);
      }
      db.createObjectStore(STORE_NAME, { keyPath: "id" });
    };
    request.onsuccess = () => {
      // The open landed after the wait was given up on; nothing holds the
      // connection now, and leaving it open blocks every other tab's upgrade.
      if (abandoned) return request.result.close();
      resolve(request.result);
    };
    request.onerror = () => reject(request.error);
    // Another tab on an older version holds the upgrade off, and none of the
    // handlers above fires meanwhile: without this the caller waits forever.
    request.onblocked = () => {
      abandoned = true;
      reject(new Error("Pending asset storage is open in another tab"));
    };
  });
}

// Storage is a best effort: a private window, a blocked origin or a failed
// upgrade must cost the player nothing, so every path resolves to null.
async function withStore<T>(
  mode: IDBTransactionMode,
  run: (store: IDBObjectStore) => IDBRequest,
): Promise<T | null> {
  if (typeof indexedDB === "undefined") return null;

  let db: IDBDatabase;
  try {
    db = await openDatabase();
  } catch (error) {
    console.error("Pending asset storage unavailable", error);
    return null;
  }

  try {
    return await new Promise<T>((resolve, reject) => {
      const transaction = db.transaction(STORE_NAME, mode);
      const request = run(transaction.objectStore(STORE_NAME));
      // A delete that resolves on the request alone can still be rolled back,
      // which is how a row survives its own removal and syncs forever.
      transaction.oncomplete = () => resolve(request.result as T);
      transaction.onabort = () => reject(transaction.error);
      request.onerror = () => reject(request.error);
    });
  } catch (error) {
    console.error("Pending asset storage failed", error);
    return null;
  } finally {
    // The connection closes once the transaction above commits.
    db.close();
  }
}

function currentUserId(): number | null {
  return storeAuth().user?.id ?? null;
}

const pendingAssetStore: PendingAssetStore = {
  // A browser is shared: rows belong to the account that captured them, or one
  // user's progress lands in the account of whoever signs in next.
  async list() {
    const rows =
      (await withStore<PendingAsset[]>("readonly", (store) =>
        store.getAll(),
      )) ?? [];
    const userId = currentUserId();
    return rows.filter((row) => row.userId === userId);
  },
  async write(entry) {
    await withStore("readwrite", (store) =>
      store.put({ ...entry, userId: currentUserId() }),
    );
  },
  async clear(id) {
    await withStore("readwrite", (store) => store.delete(id));
  },
};

export default pendingAssetStore;

/** What the browser is still holding for a rom, save and state apart. */
export async function pendingAssetKinds(
  romId: number,
): Promise<Set<PendingAssetKind>> {
  const entries = await pendingAssetStore.list();
  return new Set(
    entries
      .filter((entry) => entry.romId === romId && !accepted.has(entry.id))
      .map((entry) => entry.kind),
  );
}

// Rows the server has taken. A delete that does not stick would otherwise have
// this upload the same progress again on the next pass, and again after that.
const accepted = new Set<string>();

async function uploadSave(
  entry: PendingAsset,
  rom: DetailedRomSchema,
): Promise<PromiseSettledResult<unknown> | undefined> {
  const slot = entry.slot ?? AUTOSAVE_SLOT;
  const uploaded = await saveApi.uploadSaves({
    rom,
    emulator: entry.emulator,
    deviceId: entry.deviceId,
    slot,
    autocleanup: slot === AUTOSAVE_SLOT,
    // The dedupe is the point: a retry of bytes the server already has must
    // return that version, not mint another one.
    overwrite: false,
    savesToUpload: [
      {
        saveFile: sessionSaveFile(rom, null, entry.bytes),
        screenshotFile: entry.screenshotBytes
          ? new File(
              [entry.screenshotBytes],
              `${rom.fs_name_no_ext.trim()}.png`,
              { type: "application/octet-stream" },
            )
          : undefined,
      },
    ],
  });
  return uploaded[0];
}

async function uploadState(
  entry: PendingAsset,
  rom: DetailedRomSchema,
): Promise<PromiseSettledResult<unknown> | undefined> {
  // The backend files a state under the row already at that name, so pinning
  // the name to the capture has a retry update it rather than duplicate it.
  const name = sessionStateName(rom, new Date(entry.capturedAt));
  const uploaded = await stateApi.uploadStates({
    rom,
    emulator: entry.emulator,
    statesToUpload: [
      {
        stateFile: new File([entry.bytes], `${name}.state`, {
          type: "application/octet-stream",
        }),
        screenshotFile: entry.screenshotBytes
          ? new File([entry.screenshotBytes], `${name}.png`, {
              type: "application/octet-stream",
            })
          : undefined,
      },
    ],
  });
  return uploaded[0];
}

// A server that is failing, a network that is down and an expired session all
// deserve another pass; anything else the server answers with is its verdict.
const RETRYABLE_STATUSES = new Set([401, 408, 425, 429]);

/**
 * Why the server refused this asset for good, if it did.
 *
 * Returns:
 *   The reason to show the player, or null when the attempt is worth repeating.
 */
function permanentRefusal(error: unknown): string | null {
  if (!axios.isAxiosError(error) || !error.response) return null;
  const { status, statusText, data } = error.response;
  if (status >= 500 || RETRYABLE_STATUSES.has(status)) return null;
  // The interceptor has already fetched a fresh token for this one.
  if (isCsrfFailure(error)) return null;
  const detail = data?.detail;
  return (typeof detail === "string" && detail) || statusText || error.message;
}

interface AssetOutcome {
  asset: SyncedAsset;
  /** Set when the server refused it for good and the row was dropped. */
  reason?: string;
}

// A row the server has answered for is no longer owed, refused as much as
// taken: holding a refusal back would only retry it for the rest of time.
async function settle(
  entry: PendingAsset,
  rom: DetailedRomSchema | null,
  reason?: string,
): Promise<AssetOutcome> {
  accepted.add(entry.id);
  await pendingAssetStore.clear(entry.id);
  return {
    asset: {
      kind: entry.kind,
      romId: entry.romId,
      name: rom?.name ?? rom?.fs_name_no_ext ?? entry.romName,
      cover: rom?.path_cover_small,
    },
    reason,
  };
}

async function uploadPendingAsset(
  entry: PendingAsset,
  roms: Map<number, DetailedRomSchema>,
): Promise<AssetOutcome | null> {
  if (accepted.has(entry.id)) return null;
  if (!entry.bytes?.byteLength) {
    await pendingAssetStore.clear(entry.id);
    return null;
  }

  let rom: DetailedRomSchema | null = roms.get(entry.romId) ?? null;
  try {
    rom ??= (await romApi.getRom({ romId: entry.romId })).data;
    roms.set(entry.romId, rom);
    const upload =
      entry.kind === "state"
        ? await uploadState(entry, rom)
        : await uploadSave(entry, rom);
    if (upload?.status === "fulfilled") return settle(entry, rom);

    const refusal = permanentRefusal(
      upload?.status === "rejected" ? upload.reason : null,
    );
    return refusal ? settle(entry, rom, refusal) : null;
  } catch (error) {
    const refusal = permanentRefusal(error);
    if (refusal) return settle(entry, rom, refusal);
    console.error("Pending asset sync failed", error);
    return null;
  }
}

/** An asset the server has just taken, named so the toast can say which game. */
export interface SyncedAsset {
  kind: PendingAssetKind;
  romId: number;
  name: string;
  cover?: string | null;
}

/** One the server refused for good, dropped rather than retried forever. */
export interface DroppedAsset extends SyncedAsset {
  reason: string;
}

export interface PendingSyncResult {
  synced: SyncedAsset[];
  dropped: DroppedAsset[];
}

/**
 * Hands the server what the browser is still holding.
 *
 * Args:
 *   kinds: What to hand over, for a caller that owns one of them itself.
 *
 * Returns:
 *   What the server took, so their views can refresh and say so, and what it
 *   refused for good, so the player is told why it is gone.
 */
export async function syncPendingAssets(
  kinds: readonly PendingAssetKind[] = ["save", "state"],
): Promise<PendingSyncResult> {
  const synced: SyncedAsset[] = [];
  const dropped: DroppedAsset[] = [];
  // Several captures of one game are the common case, and they all need the
  // same rom to name themselves and their files.
  const roms = new Map<number, DetailedRomSchema>();
  for (const entry of await pendingAssetStore.list()) {
    if (!kinds.includes(entry.kind)) continue;
    const outcome = await uploadPendingAsset(entry, roms);
    if (!outcome) continue;
    if (outcome.reason === undefined) synced.push(outcome.asset);
    else dropped.push({ ...outcome.asset, reason: outcome.reason });
  }
  return { synced, dropped };
}

/** Whether anything is still owed, ignoring rows a delete failed to remove. */
export async function hasPendingAssets(): Promise<boolean> {
  const entries = await pendingAssetStore.list();
  return entries.some((entry) => !accepted.has(entry.id));
}
