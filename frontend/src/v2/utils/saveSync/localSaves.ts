// Each RomM account's copy of what its web players saved, per rom and slot,
// so device sync compares one shape whatever the player's own storage.
import { inTransaction, openDb, settle } from "@/v2/utils/idb";

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

function openDatabase(): Promise<IDBDatabase> {
  return openDb(
    DB_NAME,
    DB_VERSION,
    (request) => {
      const store = request.result.createObjectStore(STORE_NAME, {
        keyPath: ["userId", "romId", "slot"],
      });
      store.createIndex(USER_ROM_INDEX, ["userId", "romId"]);
    },
    "Save sync storage",
  );
}

async function withStore<T>(
  mode: IDBTransactionMode,
  run: (store: IDBObjectStore) => Promise<T>,
): Promise<T> {
  return inTransaction(await openDatabase(), STORE_NAME, mode, run);
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
