import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import pendingSaveStore, {
  pendingSaveRomIds,
  syncPendingSaves,
} from "@/services/pending-save";

// happy-dom ships no IndexedDB, which is also what a locked-down origin or a
// private window looks like. Losing the frame must never cost the player a save.
describe("pendingSaveStore without IndexedDB", () => {
  beforeEach(() => {
    vi.spyOn(console, "error").mockImplementation(() => undefined);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("lists nothing rather than throwing", async () => {
    await expect(pendingSaveStore.list()).resolves.toEqual([]);
  });

  it("swallows a write", async () => {
    await expect(
      pendingSaveStore.write({
        id: "1:a",
        romId: 1,
        saveBytes: new Uint8Array([1, 2, 3]).buffer,
        capturedAt: 0,
      }),
    ).resolves.toBeUndefined();
  });

  it("swallows a clear", async () => {
    await expect(pendingSaveStore.clear("1:a")).resolves.toBeUndefined();
  });

  it("reports no rom as held when nothing is stored", async () => {
    await expect(pendingSaveRomIds()).resolves.toEqual(new Set());
  });

  it("has nothing to hand over", async () => {
    await expect(syncPendingSaves()).resolves.toEqual([]);
  });
});
