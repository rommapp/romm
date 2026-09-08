import { AxiosError } from "axios";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import storeCollections, { type VirtualCollection } from "@/stores/collections";

const { getVirtualCollection, getVirtualCollections } = vi.hoisted(() => ({
  getVirtualCollection: vi.fn(),
  getVirtualCollections: vi.fn(),
}));

vi.mock("@/services/api/collection", () => ({
  default: { getVirtualCollection, getVirtualCollections },
}));

function httpError(status: number) {
  return Object.assign(new AxiosError(`HTTP ${status}`), {
    response: { status },
  });
}

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
    getVirtualCollection.mockReset();
    getVirtualCollections.mockReset();
  });

  // A response in flight left the server before the change did, so it cannot
  // stand in for the re-read.
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

  // A rescan can take a collection below the ROM threshold that generates it,
  // and a cached tile for it would outlive the collection itself.
  it("drops the cached copy when the server says the collection is gone", async () => {
    const collections = storeCollections();
    collections.setVirtualCollections([virtualCollection(8)]);
    getVirtualCollection.mockRejectedValueOnce(httpError(404));

    await expect(
      collections.refreshVirtualCollection("collection-zelda"),
    ).resolves.toBeNull();
    expect(collections.virtualCollections).toEqual([]);
  });

  it("keeps the cached copy when the read itself failed", async () => {
    const collections = storeCollections();
    collections.setVirtualCollections([virtualCollection(8)]);
    getVirtualCollection.mockRejectedValueOnce(httpError(500));

    await expect(
      collections.refreshVirtualCollection("collection-zelda"),
    ).resolves.toBeNull();
    expect(collections.virtualCollections).toHaveLength(1);
  });
});
