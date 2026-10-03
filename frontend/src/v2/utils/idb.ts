/** The result of an IndexedDB request, once it succeeds. */
export function settle<T>(request: IDBRequest<T>): Promise<T> {
  return new Promise((resolve, reject) => {
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
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
      transaction.onerror = () => reject(transaction.error);
      transaction.onabort = () => reject(transaction.error);
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
