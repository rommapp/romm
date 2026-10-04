import { inTransaction, openDb, settle } from "@/v2/utils/idb";
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

// Laid out as IDBFS lays it out, so the player opens it without an upgrade.
function upgradeSaveDb(request: IDBOpenDBRequest) {
  const db = request.result;
  const store = db.objectStoreNames.contains(IDBFS_STORE)
    ? request.transaction!.objectStore(IDBFS_STORE)
    : db.createObjectStore(IDBFS_STORE);
  if (!store.indexNames.contains(IDBFS_TIMESTAMP_INDEX)) {
    store.createIndex(IDBFS_TIMESTAMP_INDEX, IDBFS_TIMESTAMP_INDEX, {
      unique: false,
    });
  }
}

function openSaveDb(game: string): Promise<IDBDatabase> {
  return openDb(
    saveDir(game),
    IDBFS_VERSION,
    upgradeSaveDb,
    "EasyRPG save storage",
  );
}

async function withSaveStore<T>(
  game: string,
  mode: IDBTransactionMode,
  run: (store: IDBObjectStore) => Promise<T>,
): Promise<T> {
  return inTransaction(await openSaveDb(game), IDBFS_STORE, mode, run);
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

/** Remove the files named `fileNames` from the player's save folder. */
export function deleteEasyRpgSaves(
  game: string,
  fileNames: string[],
): Promise<void> {
  if (fileNames.length === 0) return Promise.resolve();
  return withSaveStore(game, "readwrite", async (store) => {
    await Promise.all(
      fileNames.map((fileName) =>
        settle(store.delete(`${saveDir(game)}/${fileName}`)),
      ),
    );
  });
}
