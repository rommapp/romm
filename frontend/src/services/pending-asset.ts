// Saves and states the server has not taken yet, held in the browser with the
// frame captured when the game wrote them, until a later pass hands them over.
import axios from "axios";
import { isCsrfFailure } from "@/services/api";
import romApi from "@/services/api/rom";
import saveApi, {
  AUTOSAVE_SLOT,
  sessionSaveFile,
  sessionScreenshotFile,
} from "@/services/api/save";
import stateApi, { sessionStateFiles } from "@/services/api/state";
import storeAuth from "@/stores/auth";
import { errorMessage } from "@/v2/utils/errorMessage";

const DB_NAME = "romm-player";
const DB_VERSION = 5;
const STORE_NAME = "pending-assets";
// Answers "what does this account still owe" from keys alone, so the question
// never deserializes the saves, states and frames the rows carry.
const OWNER_INDEX = "owner-kind-rom";

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
  /** The rom's file stem, which names the files a retry uploads. */
  fsNameNoExt?: string;
  cover?: string | null;
  bytes: ArrayBuffer;
  screenshotBytes?: ArrayBuffer;
  /** Saves only: the slot the session was writing to. */
  slot?: string;
  emulator?: string;
  /** Saves only: the device the session was playing on. */
  deviceId?: string;
  capturedAt: number;
}

interface HeldKey {
  id: string;
  kind: PendingAssetKind;
  romId: number;
}

// `crypto.randomUUID` needs a secure context, which plain http on a LAN address
// is not. The id only has to be unique within a browser.
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

function openDatabase(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);
    let abandoned = false;
    // The rows are the player's unsynced progress, so an upgrade keeps them:
    // it only drops the stores this version has stopped using.
    request.onupgradeneeded = () => {
      const db = request.result;
      const names = Array.from(db.objectStoreNames);
      for (const name of names) {
        if (name !== STORE_NAME) db.deleteObjectStore(name);
      }
      const store = names.includes(STORE_NAME)
        ? request.transaction!.objectStore(STORE_NAME)
        : db.createObjectStore(STORE_NAME, { keyPath: "id" });
      if (!store.indexNames.contains(OWNER_INDEX)) {
        store.createIndex(OWNER_INDEX, ["userId", "kind", "romId"]);
      }
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

// Rows the server has taken. A delete that does not stick would otherwise have
// this upload the same progress again on the next pass, and again after that.
const accepted = new Set<string>();

// A browser is shared: rows belong to the account that captured them, or one
// user's progress lands in the account of whoever signs in next.
async function heldKeys(
  kinds: readonly PendingAssetKind[],
): Promise<HeldKey[]> {
  const userId = currentUserId();
  const held: HeldKey[] = [];
  if (userId === null) return held;
  await withStore("readonly", (store) => {
    const request = store.index(OWNER_INDEX).openKeyCursor();
    request.onsuccess = () => {
      const cursor = request.result;
      if (!cursor) return;
      const [owner, kind, romId] = cursor.key as [
        number,
        PendingAssetKind,
        number,
      ];
      const id = cursor.primaryKey as string;
      if (owner === userId && kinds.includes(kind) && !accepted.has(id)) {
        held.push({ id, kind, romId });
      }
      cursor.continue();
    };
    return request;
  });
  return held;
}

const pendingAssetStore = {
  /**
   * Holds a capture for the account signed in.
   *
   * Returns:
   *   Whether the browser kept it, which a private window does not.
   */
  async write(entry: PendingAsset): Promise<boolean> {
    const key = await withStore<IDBValidKey>("readwrite", (store) =>
      store.put({ ...entry, userId: currentUserId() }),
    );
    return key !== null;
  },
  async clear(id: string) {
    await withStore("readwrite", (store) => store.delete(id));
  },
};

export default pendingAssetStore;

/** What the browser is still holding for a rom, save and state apart. */
export async function pendingAssetKinds(
  romId: number,
): Promise<Set<PendingAssetKind>> {
  const held = await heldKeys(["save", "state"]);
  return new Set(
    held.filter((row) => row.romId === romId).map((row) => row.kind),
  );
}

// An older row carries no file stem, so the rom is asked for its own.
async function uploadTarget(
  entry: PendingAsset,
): Promise<{ id: number; fs_name_no_ext: string }> {
  if (entry.fsNameNoExt) {
    return { id: entry.romId, fs_name_no_ext: entry.fsNameNoExt };
  }
  return (await romApi.getRom({ romId: entry.romId })).data;
}

async function uploadSave(
  entry: PendingAsset,
  rom: { id: number; fs_name_no_ext: string },
): Promise<PromiseSettledResult<unknown> | undefined> {
  const slot = entry.slot ?? AUTOSAVE_SLOT;
  const [uploaded] = await saveApi.uploadSaves({
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
          ? sessionScreenshotFile(rom, null, entry.screenshotBytes)
          : undefined,
      },
    ],
  });
  return uploaded;
}

async function uploadState(
  entry: PendingAsset,
  rom: { id: number; fs_name_no_ext: string },
): Promise<PromiseSettledResult<unknown> | undefined> {
  // The backend files a state under the row already at that name, so pinning
  // the name to the capture has a retry update it rather than duplicate it.
  const [uploaded] = await stateApi.uploadStates({
    rom,
    emulator: entry.emulator,
    statesToUpload: [
      sessionStateFiles(
        rom,
        new Date(entry.capturedAt),
        entry.bytes,
        entry.screenshotBytes,
      ),
    ],
  });
  return uploaded;
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
  const { status } = error.response;
  if (status >= 500 || RETRYABLE_STATUSES.has(status)) return null;
  // The interceptor has already fetched a fresh token for this one.
  if (isCsrfFailure(error)) return null;
  return errorMessage(error);
}

// A row the server has answered for, taken or refused, is no longer owed.
async function settle(entry: PendingAsset): Promise<SyncedAsset> {
  accepted.add(entry.id);
  await pendingAssetStore.clear(entry.id);
  return {
    kind: entry.kind,
    romId: entry.romId,
    name: entry.romName,
    cover: entry.cover,
  };
}

async function uploadPendingAsset(
  entry: PendingAsset,
): Promise<SyncedAsset | DroppedAsset | null> {
  if (!entry.bytes?.byteLength) {
    await pendingAssetStore.clear(entry.id);
    return null;
  }

  try {
    const rom = await uploadTarget(entry);
    const upload =
      entry.kind === "state"
        ? await uploadState(entry, rom)
        : await uploadSave(entry, rom);
    if (upload?.status === "fulfilled") return settle(entry);
    // A refusal is judged in the same place as a request that never landed.
    throw upload?.status === "rejected"
      ? upload.reason
      : new Error("The server returned no upload result");
  } catch (error) {
    const reason = permanentRefusal(error);
    if (reason) return { ...(await settle(entry)), reason };
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

/** One the server refused for good, and dropped from the browser. */
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
  // One row at a time, so a queue of large states is never all in memory.
  for (const { id } of await heldKeys(kinds)) {
    const entry = await withStore<PendingAsset>("readonly", (store) =>
      store.get(id),
    );
    if (!entry) continue;
    const outcome = await uploadPendingAsset(entry);
    if (!outcome) continue;
    if ("reason" in outcome) dropped.push(outcome);
    else synced.push(outcome);
  }
  return { synced, dropped };
}

/** Whether anything of these kinds is still owed. */
export async function hasPendingAssets(
  kinds: readonly PendingAssetKind[] = ["save", "state"],
): Promise<boolean> {
  return (await heldKeys(kinds)).length > 0;
}
