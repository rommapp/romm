// Saves the server has not accepted yet, held in the browser with the frame
// captured at the moment the game wrote them. A sync that fails offline would
// otherwise lose that frame and picture a later moment on the retry, and a
// closed tab would lose the progress outright.
import romApi from "@/services/api/rom";
import saveApi, { AUTOSAVE_SLOT, sessionSaveFile } from "@/services/api/save";

const DB_NAME = "romm-player";
const DB_VERSION = 1;
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
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        db.createObjectStore(STORE_NAME, { keyPath: "id" });
      }
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
      const request = run(
        db.transaction(STORE_NAME, mode).objectStore(STORE_NAME),
      );
      request.onsuccess = () => resolve(request.result as T);
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
  return new Set(entries.map((entry) => entry.romId));
}

async function uploadPendingSave(entry: PendingSave): Promise<boolean> {
  if (!entry.saveBytes?.byteLength) {
    await pendingSaveStore.clear(entry.id);
    return false;
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
      // Progress the server never saw, so the stale-device guard and the hash
      // dedupe have nothing to compare it against.
      overwrite: true,
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

    if (uploaded[0]?.status !== "fulfilled") return false;
    await pendingSaveStore.clear(entry.id);
    return true;
  } catch (error) {
    console.error("Pending save sync failed", error);
    return false;
  }
}

/**
 * Hands the server everything the browser is still holding.
 *
 * Returns:
 *   The rom ids the server took, so their views can refresh.
 */
export async function syncPendingSaves(): Promise<number[]> {
  const synced: number[] = [];
  for (const entry of await pendingSaveStore.list()) {
    if (await uploadPendingSave(entry)) synced.push(entry.romId);
  }
  return synced;
}
