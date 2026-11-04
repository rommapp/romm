/** The result of an IndexedDB request, once it succeeds. */
export function settle<T>(request: IDBRequest<T>): Promise<T> {
  return new Promise((resolve, reject) => {
    request.onsuccess = () => resolve(request.result);
    request.onerror = () =>
      reject(request.error ?? new Error("IndexedDB request failed"));
  });
}

/**
 * Open the database `name` at `version`, running `upgrade` when it is older.
 *
 * Args:
 *   label: What the database holds, for the error when another tab blocks it.
 */
export function openDb(
  name: string,
  version: number,
  upgrade: (request: IDBOpenDBRequest) => void,
  label: string,
): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(name, version);
    let abandoned = false;
    request.onupgradeneeded = () => upgrade(request);
    request.onsuccess = () => {
      // Opened after the wait was given up on; left open it blocks other tabs.
      if (abandoned) return request.result.close();
      resolve(request.result);
    };
    request.onerror = () =>
      reject(request.error ?? new Error(`Could not open ${label}`));
    // Another tab on an older version holds the upgrade off, and no other
    // handler fires meanwhile, so without this the caller waits forever.
    request.onblocked = () => {
      abandoned = true;
      reject(new Error(`${label} is open in another tab`));
    };
  });
}

/** Run `run` in one transaction on `storeName`, then close `db` once it commits. */
export async function inTransaction<T>(
  db: IDBDatabase,
  storeName: string,
  mode: IDBTransactionMode,
  run: (store: IDBObjectStore) => Promise<T>,
): Promise<T> {
  try {
    const transaction = db.transaction(storeName, mode);
    const committed = new Promise<void>((resolve, reject) => {
      transaction.oncomplete = () => resolve();
      transaction.onerror = () =>
        reject(transaction.error ?? new Error("IndexedDB transaction failed"));
      transaction.onabort = () =>
        reject(transaction.error ?? new Error("IndexedDB transaction aborted"));
    });
    const [result] = await Promise.all([
      run(transaction.objectStore(storeName)),
      committed,
    ]);
    return result;
  } finally {
    db.close();
  }
}
