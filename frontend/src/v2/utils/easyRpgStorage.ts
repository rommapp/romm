import type { PlayerSaveFile } from "@/v2/utils/saveSync";

// The EasyRPG web player keeps a game's saves in an Emscripten IDBFS
// database named after the folder it mounts them at, `/easyrpg/<game>/Save`.
const IDBFS_VERSION = 21;
const IDBFS_STORE = "FILE_DATA";
const IDBFS_TIMESTAMP_INDEX = "timestamp";
// A regular file, readable and writable by all, as Emscripten creates one.
const IDBFS_FILE_MODE = 0o100666;

const SAVE_FILE = /^(save\d+)\.lsd$/i;
const SAVE_EXTENSION = ".lsd";

interface IdbfsEntry {
  timestamp: Date;
  mode: number;
  contents?: Uint8Array;
}

/** The game name the player is launched with, which also names its saves. */
export function easyRpgGameName(romId: number, userId: number): string {
  return `${romId}-${userId}`;
}

function saveDir(game: string): string {
  // The player lowercases the game name before mounting.
  return `/easyrpg/${game.toLowerCase()}/Save`;
}

function settle<T>(request: IDBRequest<T>): Promise<T> {
  return new Promise((resolve, reject) => {
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

function openSaveDb(game: string): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(saveDir(game), IDBFS_VERSION);
    // Laid out as IDBFS lays it out, so the player opens it without an upgrade.
    request.onupgradeneeded = () => {
      const db = request.result;
      const store = db.objectStoreNames.contains(IDBFS_STORE)
        ? request.transaction!.objectStore(IDBFS_STORE)
        : db.createObjectStore(IDBFS_STORE);
      if (!store.indexNames.contains(IDBFS_TIMESTAMP_INDEX)) {
        store.createIndex(IDBFS_TIMESTAMP_INDEX, IDBFS_TIMESTAMP_INDEX, {
          unique: false,
        });
      }
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
    request.onblocked = () =>
      reject(new Error("EasyRPG save storage is open in another tab"));
  });
}

async function withSaveStore<T>(
  game: string,
  mode: IDBTransactionMode,
  run: (store: IDBObjectStore) => Promise<T>,
): Promise<T> {
  const db = await openSaveDb(game);
  try {
    const transaction = db.transaction(IDBFS_STORE, mode);
    const committed = new Promise<void>((resolve, reject) => {
      transaction.oncomplete = () => resolve();
      transaction.onerror = () => reject(transaction.error);
      transaction.onabort = () => reject(transaction.error);
    });
    const [result] = await Promise.all([
      run(transaction.objectStore(IDBFS_STORE)),
      committed,
    ]);
    return result;
  } finally {
    db.close();
  }
}

/** The save files the player holds for `game`, one slot per `SaveNN.lsd`. */
export function readEasyRpgSaves(game: string): Promise<PlayerSaveFile[]> {
  const prefix = `${saveDir(game)}/`;
  return withSaveStore(game, "readonly", async (store) => {
    const [keys, entries] = await Promise.all([
      settle(store.getAllKeys()),
      settle(store.getAll() as IDBRequest<IdbfsEntry[]>),
    ]);
    const saves: PlayerSaveFile[] = [];
    keys.forEach((key, index) => {
      const entry = entries[index];
      if (
        typeof key !== "string" ||
        !key.startsWith(prefix) ||
        !entry?.contents
      )
        return;
      const fileName = key.slice(prefix.length);
      const match = SAVE_FILE.exec(fileName);
      if (!match) return;
      saves.push({
        slot: match[1]!,
        fileName,
        bytes: entry.contents,
        updatedAt: entry.timestamp.getTime(),
      });
    });
    return saves;
  });
}

/** Hand `saves` to the player, which loads them when it next starts `game`. */
export function writeEasyRpgSaves(
  game: string,
  saves: { slot: string; bytes: Uint8Array; updatedAt: number }[],
): Promise<void> {
  if (saves.length === 0) return Promise.resolve();
  return withSaveStore(game, "readwrite", async (store) => {
    await Promise.all(
      saves.map((save) =>
        settle(
          store.put(
            {
              timestamp: new Date(save.updatedAt),
              mode: IDBFS_FILE_MODE,
              contents: save.bytes,
            } satisfies IdbfsEntry,
            `${saveDir(game)}/${save.slot}${SAVE_EXTENSION}`,
          ),
        ),
      ),
    );
  });
}
