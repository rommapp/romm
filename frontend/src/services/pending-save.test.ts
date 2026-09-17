import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import pendingSaveStore from "@/services/pending-save";

// happy-dom ships no IndexedDB, which is also what a locked-down origin or a
// private window looks like. Losing the frame must never cost the player a save.
describe("pendingSaveStore without IndexedDB", () => {
  beforeEach(() => {
    vi.spyOn(console, "error").mockImplementation(() => undefined);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("reads nothing rather than throwing", async () => {
    await expect(pendingSaveStore.read(1)).resolves.toBeNull();
  });

  it("swallows a write", async () => {
    await expect(
      pendingSaveStore.write({
        romId: 1,
        saveBytes: new Uint8Array([1, 2, 3]).buffer,
        capturedAt: 0,
      }),
    ).resolves.toBeUndefined();
  });

  it("swallows a clear", async () => {
    await expect(pendingSaveStore.clear(1)).resolves.toBeUndefined();
  });
});
