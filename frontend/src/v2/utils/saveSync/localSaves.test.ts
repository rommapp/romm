import "fake-indexeddb/auto";
import { describe, expect, it } from "vitest";
import {
  deleteLocalSave,
  listLocalSaves,
  putLocalSave,
  type LocalSave,
} from "./localSaves";

function localSave(overrides: Partial<LocalSave> = {}): LocalSave {
  return {
    userId: 1,
    romId: 10,
    slot: "autosave",
    fileName: "game.srm",
    emulator: "easyrpg",
    bytes: new Uint8Array([1, 2, 3]),
    updatedAt: 1000,
    hash: "abc",
    syncedHash: null,
    ...overrides,
  };
}

describe("local saves", () => {
  it("keeps one copy per slot, apart for each account and rom", async () => {
    await putLocalSave(localSave({ slot: "Save01" }));
    await putLocalSave(localSave({ slot: "Save01", hash: "newer" }));
    await putLocalSave(localSave({ slot: "Save02" }));
    await putLocalSave(localSave({ userId: 2, slot: "Save01" }));
    await putLocalSave(localSave({ romId: 11, slot: "Save01" }));

    const saves = await listLocalSaves(1, 10);

    expect(saves.map((save) => [save.slot, save.hash])).toEqual([
      ["Save01", "newer"],
      ["Save02", "abc"],
    ]);
    expect(saves[0]!.bytes).toEqual(new Uint8Array([1, 2, 3]));
  });

  it("forgets a deleted slot", async () => {
    await putLocalSave(localSave({ romId: 20 }));

    await deleteLocalSave(1, 20, "autosave");

    expect(await listLocalSaves(1, 20)).toEqual([]);
  });
});
