import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import storeCollections, { type VirtualCollection } from "@/stores/collections";

const { getVirtualCollections } = vi.hoisted(() => ({
  getVirtualCollections: vi.fn(),
}));

vi.mock("@/services/api/collection", () => ({
  default: { getVirtualCollections },
}));

function virtualCollection(romCount: number): VirtualCollection {
  return {
    id: "collection-zelda",
    name: "The Legend of Zelda",
    rom_count: romCount,
  } as VirtualCollection;
}

/** A request whose response the test releases by hand. */
function deferred() {
  let settle!: (value: { data: VirtualCollection[] }) => void;
  const promise = new Promise<{ data: VirtualCollection[] }>((resolve) => {
    settle = resolve;
  });
  return { promise, settle };
}

describe("collections store virtual refresh", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    getVirtualCollections.mockReset();
  });

  // A scan or a metadata write landing mid-fetch used to hit the in-flight
  // guard and be dropped, leaving the pre-change response cached for the
  // session, which is the drift this whole change is about.
  it("re-reads after a fetch that was already in flight", async () => {
    const first = deferred();
    getVirtualCollections.mockReturnValueOnce(first.promise);
    const collections = storeCollections();

    const initial = collections.fetchVirtualCollections("collection");
    void collections.refreshVirtualCollections();

    getVirtualCollections.mockResolvedValueOnce({
      data: [virtualCollection(9)],
    });
    first.settle({ data: [virtualCollection(8)] });
    await initial;
    await vi.waitFor(() =>
      expect(collections.virtualCollections[0].rom_count).toBe(9),
    );
    expect(getVirtualCollections).toHaveBeenCalledTimes(2);
  });

  it("keeps the cached slice when the re-read fails", async () => {
    getVirtualCollections.mockResolvedValueOnce({
      data: [virtualCollection(8)],
    });
    const collections = storeCollections();
    await collections.fetchVirtualCollections("collection");

    getVirtualCollections.mockRejectedValueOnce(new Error("offline"));
    // Resolves rather than rejects: every caller fires this in the background,
    // so a rejection would surface as an unhandled one.
    await expect(collections.refreshVirtualCollections()).resolves.toEqual([]);
    expect(collections.virtualCollections[0].rom_count).toBe(8);
  });

  it("does nothing until a slice has been fetched", async () => {
    await expect(
      storeCollections().refreshVirtualCollections(),
    ).resolves.toEqual([]);
    expect(getVirtualCollections).not.toHaveBeenCalled();
  });
});
