// Saves the server has not accepted yet, held in the browser with the frame
// captured at the moment the game wrote them. A sync that fails offline would
// otherwise lose that frame and picture a later moment on the retry, and a
// closed tab would lose the progress outright.
import romApi from "@/services/api/rom";
import saveApi, { AUTOSAVE_SLOT, sessionSaveFile } from "@/services/api/save";

const DB_NAME = "romm-player";
// v2 rekeyed the store from the rom to the playing session. An upgrade cannot
// rewrite keys in place, and a row carrying the old key can never be deleted by
// the new one, so the store is rebuilt rather than migrated.
const DB_VERSION = 2;
const STORE_NAME = "pending-saves";

export interface PendingSave {
  /** One row per playing session, so two offline sessions cannot overwrite each other. */
  id: string;
  romId: number;
  saveBytes: ArrayBuffer;
  screenshotBytes?: ArrayBuffer;
  slot?: string;
  emulator?: string;
  deviceId?: string;
  capturedAt: number;
}

export interface PendingSaveStore {
  list(): Promise<PendingSave[]>;
  write(entry: PendingSave): Promise<void>;
  clear(id: string): Promise<void>;
}

function openDatabase(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);
    request.onupgradeneeded = () => {
      const db = request.result;
      if (db.objectStoreNames.contains(STORE_NAME)) {
        db.deleteObjectStore(STORE_NAME);
      }
      db.createObjectStore(STORE_NAME, { keyPath: "id" });
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
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
    console.error("Pending save storage unavailable", error);
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
    console.error("Pending save storage failed", error);
    return null;
  } finally {
    // The connection closes once the transaction above commits.
    db.close();
  }
}

const pendingSaveStore: PendingSaveStore = {
  async list() {
    return (
      (await withStore<PendingSave[]>("readonly", (store) => store.getAll())) ??
      []
    );
  },
  async write(entry) {
    await withStore("readwrite", (store) => store.put(entry));
  },
  async clear(id) {
    await withStore("readwrite", (store) => store.delete(id));
  },
};

export default pendingSaveStore;

/** The rom ids the browser is still holding progress for. */
export async function pendingSaveRomIds(): Promise<Set<number>> {
  const entries = await pendingSaveStore.list();
  return new Set(
    entries.filter((e) => !accepted.has(e.id)).map((entry) => entry.romId),
  );
}

// Rows the server has taken. A delete that does not stick would otherwise have
// this upload the same progress again on the next pass, and again after that.
const accepted = new Set<string>();

async function uploadPendingSave(
  entry: PendingSave,
): Promise<SyncedSave | null> {
  if (accepted.has(entry.id)) return null;
  if (!entry.saveBytes?.byteLength) {
    await pendingSaveStore.clear(entry.id);
    return null;
  }

  try {
    const { data: rom } = await romApi.getRom({ romId: entry.romId });
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
          saveFile: sessionSaveFile(rom, null, entry.saveBytes),
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

    if (uploaded[0]?.status !== "fulfilled") return null;
    accepted.add(entry.id);
    await pendingSaveStore.clear(entry.id);
    return {
      romId: entry.romId,
      name: rom.name ?? rom.fs_name_no_ext,
      cover: rom.path_cover_small,
    };
  } catch (error) {
    console.error("Pending save sync failed", error);
    return null;
  }
}

/** A save the server has just taken, named so the toast can say which game. */
export interface SyncedSave {
  romId: number;
  name: string;
  cover?: string | null;
}

/**
 * Hands the server everything the browser is still holding.
 *
 * Returns:
 *   The saves the server took, so their views can refresh and say so.
 */
export async function syncPendingSaves(): Promise<SyncedSave[]> {
  const synced: SyncedSave[] = [];
  for (const entry of await pendingSaveStore.list()) {
    const result = await uploadPendingSave(entry);
    if (result) synced.push(result);
  }
  return synced;
}

/** Whether anything is still owed, ignoring rows a delete failed to remove. */
export async function hasPendingSaves(): Promise<boolean> {
  const entries = await pendingSaveStore.list();
  return entries.some((entry) => !accepted.has(entry.id));
}
