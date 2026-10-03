import "fake-indexeddb/auto";
import { describe, expect, it } from "vitest";
import {
  deleteEasyRpgSaves,
  easyRpgGameName,
  readEasyRpgSaves,
  writeEasyRpgSaves,
} from "./easyRpgStorage";

function openIdbfs(name: string): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(name, 21);
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

describe("EasyRPG storage", () => {
  it("names the game after the rom and the account", () => {
    expect(easyRpgGameName(12, 3)).toBe("12-3");
  });

  it("reads back what it wrote, one slot per save file", async () => {
    await writeEasyRpgSaves("12-3", [
      { slot: "Save01", bytes: new Uint8Array([1]), updatedAt: 1000 },
      { slot: "Save02", bytes: new Uint8Array([2]), updatedAt: 2000 },
    ]);

    const saves = await readEasyRpgSaves("12-3");

    expect(
      saves.map((save) => [
        save.slot,
        save.fileName,
        [...save.bytes],
        save.updatedAt,
      ]),
    ).toEqual([
      ["Save01", "Save01.lsd", [1], 1000],
      ["Save02", "Save02.lsd", [2], 2000],
    ]);
  });

  it("deletes the named save files", async () => {
    await writeEasyRpgSaves("30-1", [
      { slot: "Save01", bytes: new Uint8Array([1]), updatedAt: 1 },
      { slot: "Save02", bytes: new Uint8Array([2]), updatedAt: 2 },
    ]);

    await deleteEasyRpgSaves("30-1", ["Save01.lsd"]);

    expect((await readEasyRpgSaves("30-1")).map((save) => save.slot)).toEqual([
      "Save02",
    ]);
  });

  it("keeps each account's saves apart", async () => {
    await writeEasyRpgSaves("40-1", [
      { slot: "Save01", bytes: new Uint8Array([1]), updatedAt: 1 },
    ]);

    expect(await readEasyRpgSaves("40-2")).toEqual([]);
  });

  it("lays the database out as IDBFS does, so the player opens it", async () => {
    await writeEasyRpgSaves("50-1", [
      { slot: "Save01", bytes: new Uint8Array([1]), updatedAt: 1 },
    ]);

    const db = await openIdbfs("/easyrpg/50-1/Save");
    const store = db.transaction("FILE_DATA").objectStore("FILE_DATA");
    expect([...store.indexNames]).toEqual(["timestamp"]);
    db.close();
  });

  it("skips files that are not save slots", async () => {
    await writeEasyRpgSaves("60-1", [
      { slot: "Save03", bytes: new Uint8Array([3]), updatedAt: 1 },
    ]);
    const raw = await openIdbfs("/easyrpg/60-1/Save");
    await new Promise<void>((resolve) => {
      const transaction = raw.transaction("FILE_DATA", "readwrite");
      transaction.objectStore("FILE_DATA").put(
        {
          timestamp: new Date(1),
          mode: 0o100666,
          contents: new Uint8Array([9]),
        },
        "/easyrpg/60-1/Save/config.ini",
      );
      transaction.oncomplete = () => resolve();
    });
    raw.close();

    expect((await readEasyRpgSaves("60-1")).map((save) => save.slot)).toEqual([
      "Save03",
    ]);
  });
});
