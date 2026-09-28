import { AxiosError } from "axios";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import storeAuth from "@/stores/auth";
import storeCollections, {
  type Collection,
  type VirtualCollection,
} from "@/stores/collections";
import type { User } from "@/stores/users";

const { getCollections, getVirtualCollection, getVirtualCollections } =
  vi.hoisted(() => ({
    getCollections: vi.fn(),
    getVirtualCollection: vi.fn(),
    getVirtualCollections: vi.fn(),
  }));

vi.mock("@/services/api/collection", () => ({
  default: { getCollections, getVirtualCollection, getVirtualCollections },
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

function favoriteCollection(id: number, userId: number): Collection {
  return {
    id,
    name: "Favourites",
    is_favorite: true,
    is_public: true,
    user_id: userId,
    rom_ids: [],
  } as unknown as Collection;
}

describe("collections store favorites", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    getCollections.mockReset();
    storeAuth().setCurrentUser({ id: 7 } as User);
  });

  // Another user's favorites collection turns up here once they make it
  // public, and every write to it is a 403.
  it("picks the current user's favorites, not another user's public one", async () => {
    getCollections.mockResolvedValueOnce({
      data: [favoriteCollection(3, 2), favoriteCollection(5, 7)],
    });
    const collections = storeCollections();

    await collections.fetchCollections();

    expect(collections.favoriteCollection?.id).toBe(5);
  });

  it("leaves the favorites target unset when the user owns none", async () => {
    getCollections.mockResolvedValueOnce({
      data: [favoriteCollection(3, 2)],
    });
    const collections = storeCollections();

    await collections.fetchCollections();

    expect(collections.favoriteCollection).toBeUndefined();
  });
});
