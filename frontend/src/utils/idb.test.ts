import "fake-indexeddb/auto";
import { describe, expect, it, vi } from "vitest";
import { openDb } from "./idb";

describe("openDb", () => {
  it("runs the upgrade on a new database", async () => {
    const upgrade = vi.fn((request: IDBOpenDBRequest) =>
      request.result.createObjectStore("rows"),
    );

    const db = await openDb("idb-new", 1, upgrade, "Rows");

    expect(upgrade).toHaveBeenCalledOnce();
    expect([...db.objectStoreNames]).toEqual(["rows"]);
    db.close();
  });

  it("rejects instead of waiting when another tab holds an older version", async () => {
    const older = await openDb("idb-blocked", 1, () => undefined, "Rows");

    await expect(
      openDb("idb-blocked", 2, () => undefined, "Rows"),
    ).rejects.toThrow("Rows is open in another tab");
    older.close();
  });
});
