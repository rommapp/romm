import type { SaveSchema } from "@/__generated__";
import saveApi from "@/services/api/save";

// The EasyRPG web player keeps a game's saves in an Emscripten IDBFS
// database named after the folder it mounts them at, `/easyrpg/<game>/Save`.
const IDBFS_VERSION = 21;
const IDBFS_STORE = "FILE_DATA";
const IDBFS_TIMESTAMP_INDEX = "timestamp";
// A regular file, readable and writable by all, as Emscripten creates one.
const IDBFS_FILE_MODE = 0o100666;

const SAVE_FILE = /^save\d+\.lsd$/i;

export const EASYRPG_EMULATOR = "easyrpg";

export interface EasyRpgSave {
  name: string;
  bytes: Uint8Array;
  modified: Date;
}

interface IdbfsEntry {
  timestamp: Date;
  mode: number;
  contents?: Uint8Array;
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

export function isEasyRpgSaveFile(name: string): boolean {
  return SAVE_FILE.test(name);
}

/** The save files the player holds for `game` in this browser. */
export function readEasyRpgSaves(game: string): Promise<EasyRpgSave[]> {
  const prefix = `${saveDir(game)}/`;
  return withSaveStore(game, "readonly", async (store) => {
    const [keys, entries] = await Promise.all([
      settle(store.getAllKeys()),
      settle(store.getAll() as IDBRequest<IdbfsEntry[]>),
    ]);
    const saves: EasyRpgSave[] = [];
    keys.forEach((key, index) => {
      const entry = entries[index];
      if (typeof key !== "string" || !entry?.contents) return;
      const name = key.slice(prefix.length);
      if (!key.startsWith(prefix) || !isEasyRpgSaveFile(name)) return;
      saves.push({ name, bytes: entry.contents, modified: entry.timestamp });
    });
    return saves;
  });
}

/** Hand `saves` to the player, which loads them when it next starts `game`. */
export function writeEasyRpgSaves(
  game: string,
  saves: EasyRpgSave[],
): Promise<void> {
  return withSaveStore(game, "readwrite", async (store) => {
    await Promise.all(
      saves.map((save) =>
        settle(
          store.put(
            {
              timestamp: save.modified,
              mode: IDBFS_FILE_MODE,
              contents: save.bytes,
            } satisfies IdbfsEntry,
            `${saveDir(game)}/${save.name}`,
          ),
        ),
      ),
    );
  });
}

export function clearEasyRpgSaves(game: string): Promise<void> {
  return withSaveStore(game, "readwrite", async (store) => {
    await settle(store.clear());
  });
}

/** The server saves the player can load: one per in-game slot file. */
export function easyRpgServerSaves(saves: SaveSchema[]): SaveSchema[] {
  return saves.filter(
    (save) =>
      save.emulator === EASYRPG_EMULATOR &&
      !save.slot &&
      isEasyRpgSaveFile(save.file_name),
  );
}

export interface EasyRpgLaunchPlan {
  download: SaveSchema[];
  upload: EasyRpgSave[];
}

/** The newer copy of each save file wins, wherever it lives. */
export function planEasyRpgLaunch(
  server: SaveSchema[],
  local: EasyRpgSave[],
): EasyRpgLaunchPlan {
  const localByName = new Map(local.map((save) => [save.name, save]));
  const serverByName = new Map(server.map((save) => [save.file_name, save]));
  return {
    download: server.filter((save) => {
      const held = localByName.get(save.file_name);
      return !held || held.modified < new Date(save.updated_at);
    }),
    upload: local.filter((save) => {
      const stored = serverByName.get(save.name);
      return !stored || save.modified > new Date(stored.updated_at);
    }),
  };
}

function ownerKey(game: string): string {
  return `player:easyrpg:${game}:user`;
}

/** Keeps the player's browser saves for one game in step with the server. */
export class EasyRpgSaveSync {
  // Each file's modification time when it last matched the server.
  private readonly synced = new Map<string, number>();
  private readonly stored = new Map<string, SaveSchema>();
  // The latest read of the player's storage, for the unload path.
  private snapshot: EasyRpgSave[] = [];

  private readonly rom: { id: number; user_saves: SaveSchema[] };
  private readonly game: string;

  constructor(rom: { id: number; user_saves: SaveSchema[] }, game: string) {
    this.rom = rom;
    this.game = game;
  }

  private changed(saves: EasyRpgSave[]): EasyRpgSave[] {
    return saves.filter(
      (save) => this.synced.get(save.name) !== save.modified.getTime(),
    );
  }

  private remember(save: EasyRpgSave, stored: SaveSchema) {
    this.stored.set(save.name, stored);
    this.synced.set(save.name, save.modified.getTime());
  }

  /** Load the server's saves into the player before it starts. */
  async prepare(userId: number): Promise<void> {
    // Browser storage is shared by every account on the profile.
    if (readOwner(this.game) !== String(userId)) {
      await clearEasyRpgSaves(this.game);
      writeOwner(this.game, String(userId));
    }

    const server = easyRpgServerSaves(this.rom.user_saves);
    for (const save of server) this.stored.set(save.file_name, save);

    const local = await readEasyRpgSaves(this.game);
    const plan = planEasyRpgLaunch(server, local);
    const downloaded = await Promise.all(
      plan.download.map(async (save) => {
        const response = await fetch(save.download_path, {
          credentials: "same-origin",
        });
        if (!response.ok) throw new Error(`Save ${save.id} download failed`);
        return {
          name: save.file_name,
          bytes: new Uint8Array(await response.arrayBuffer()),
          modified: new Date(save.updated_at),
        };
      }),
    );
    await writeEasyRpgSaves(this.game, downloaded);

    for (const save of local)
      this.synced.set(save.name, save.modified.getTime());
    for (const save of downloaded) {
      this.synced.set(save.name, save.modified.getTime());
    }
    // A save made here that never reached the server goes up with the next push.
    for (const save of plan.upload) this.synced.delete(save.name);
  }

  /**
   * Upload every save the player wrote since the last push.
   *
   * Returns:
   *   False when a save failed to upload; it is retried on the next push.
   */
  async push(): Promise<boolean> {
    this.snapshot = await readEasyRpgSaves(this.game);
    const results = await Promise.all(
      this.changed(this.snapshot).map(async (save) => {
        const [result] = await saveApi.uploadSaves({
          rom: this.rom,
          emulator: EASYRPG_EMULATOR,
          savesToUpload: [{ saveFile: saveFileOf(save) }],
        });
        if (result?.status !== "fulfilled") return false;
        this.remember(save, result.value);
        return true;
      }),
    );
    return results.every(Boolean);
  }

  /** Send what the last push saw changing while the page goes away. */
  pushOnUnload(): void {
    for (const save of this.changed(this.snapshot)) {
      saveApi.sendSaveOnUnload({
        rom: this.rom,
        emulator: EASYRPG_EMULATOR,
        save: this.stored.get(save.name) ?? null,
        saveFile: saveFileOf(save),
      });
    }
  }
}

function saveFileOf(save: EasyRpgSave): File {
  return new File([save.bytes as BlobPart], save.name, {
    type: "application/octet-stream",
  });
}

function readOwner(game: string): string | null {
  try {
    return localStorage.getItem(ownerKey(game));
  } catch {
    return null;
  }
}

function writeOwner(game: string, userId: string) {
  try {
    localStorage.setItem(ownerKey(game), userId);
  } catch {
    // Without storage the next launch clears the saves again, which is safe.
  }
}
