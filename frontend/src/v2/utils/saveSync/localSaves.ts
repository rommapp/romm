// Each RomM account's copy of what its web players saved, per rom and slot.
// The players' own storage is restored from here before a launch and copied
// back after, so device sync has one shape to compare whatever the player.
const DB_NAME = "romm-saves";
const DB_VERSION = 1;
const STORE_NAME = "saves";
const USER_ROM_INDEX = "user-rom";

export interface LocalSave {
  userId: number;
  romId: number;
  slot: string;
  fileName: string;
  emulator: string;
  bytes: Uint8Array;
  /** When the player wrote this copy, or the server's time for a download. */
  updatedAt: number;
  hash: string;
  /** The hash the server last held for the slot, so a push sends only changes. */
  syncedHash: string | null;
}

function settle<T>(request: IDBRequest<T>): Promise<T> {
  return new Promise((resolve, reject) => {
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

function openDatabase(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);
    request.onupgradeneeded = () => {
      const store = request.result.createObjectStore(STORE_NAME, {
        keyPath: ["userId", "romId", "slot"],
      });
      store.createIndex(USER_ROM_INDEX, ["userId", "romId"]);
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

async function withStore<T>(
  mode: IDBTransactionMode,
  run: (store: IDBObjectStore) => Promise<T>,
): Promise<T> {
  const db = await openDatabase();
  try {
    const transaction = db.transaction(STORE_NAME, mode);
    const committed = new Promise<void>((resolve, reject) => {
      transaction.oncomplete = () => resolve();
      transaction.onerror = () => reject(transaction.error);
      transaction.onabort = () => reject(transaction.error);
    });
    const [result] = await Promise.all([
      run(transaction.objectStore(STORE_NAME)),
      committed,
    ]);
    return result;
  } finally {
    db.close();
  }
}

export function listLocalSaves(
  userId: number,
  romId: number,
): Promise<LocalSave[]> {
  return withStore("readonly", (store) =>
    settle(
      store.index(USER_ROM_INDEX).getAll([userId, romId]) as IDBRequest<
        LocalSave[]
      >,
    ),
  );
}

export function putLocalSave(save: LocalSave): Promise<void> {
  return withStore("readwrite", async (store) => {
    await settle(store.put(save));
  });
}

export function deleteLocalSave(
  userId: number,
  romId: number,
  slot: string,
): Promise<void> {
  return withStore("readwrite", async (store) => {
    await settle(store.delete([userId, romId, slot]));
  });
}
