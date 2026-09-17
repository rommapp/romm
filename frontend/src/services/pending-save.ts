// An in-game save the server has not accepted yet, held in the browser with the
// frame captured at the moment the game wrote it. A sync that fails offline
// would otherwise lose that frame and picture a later moment on the retry.

const DB_NAME = "romm-player";
const DB_VERSION = 1;
const STORE_NAME = "pending-saves";

export interface PendingSave {
  romId: number;
  saveBytes: ArrayBuffer;
  screenshotBytes?: ArrayBuffer;
  slot?: string;
  emulator?: string;
  capturedAt: number;
}

export interface PendingSaveStore {
  read(romId: number): Promise<PendingSave | null>;
  write(entry: PendingSave): Promise<void>;
  clear(romId: number): Promise<void>;
}

function openDatabase(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);
    request.onupgradeneeded = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        db.createObjectStore(STORE_NAME, { keyPath: "romId" });
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

const indexedDbStore: PendingSaveStore = {
  async read(romId) {
    const entry = await withStore<PendingSave | undefined>(
      "readonly",
      (store) => store.get(romId),
    );
    return entry ?? null;
  },
  async write(entry) {
    await withStore("readwrite", (store) => store.put(entry));
  },
  async clear(romId) {
    await withStore("readwrite", (store) => store.delete(romId));
  },
};

export default indexedDbStore;
