import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import storeCollections, { type Collection } from "@/stores/collections";
import storeGalleryFilter from "@/stores/galleryFilter";
import type { Platform } from "@/stores/platforms";
import storeRoms, { type DetailedRom, type SimpleRom } from "@/stores/roms";
import storeGalleryRoms from "@/v2/stores/galleryRoms";
import storeGallerySelection from "@/v2/stores/gallerySelection";
import { useRomSync } from "./index";

const { getRoms } = vi.hoisted(() => ({ getRoms: vi.fn() }));

vi.mock("@/services/api/rom", () => ({
  default: { getRoms },
}));

function makeRom(overrides: Partial<SimpleRom> = {}): SimpleRom {
  return {
    id: 1,
    name: "Chrono Trigger",
    ...overrides,
  } as unknown as SimpleRom;
}

/** Put the gallery in a platform context with one loaded window so
 * `onGalleryView` holds and there's cached state to invalidate. */
function seedGallery(rom: SimpleRom, position = 3) {
  const gallery = storeGalleryRoms();
  gallery.setCurrentPlatform({ id: 1 } as unknown as Platform);
  gallery.byPosition.set(position, rom);
  gallery.loadedWindows.add(0);
  gallery.metadataLoaded = true;
  gallery.total = 1;
  return gallery;
}

describe("useRomSync", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    getRoms.mockReset();
    getRoms.mockResolvedValue({
      data: { total: 0, items: [], char_index: {}, rom_id_index: [] },
    });
  });

  it("syncCachedRom refreshes every surface rendering the ROM", () => {
    const gallery = seedGallery(makeRom({ name: "old" }));
    const romsStore = storeRoms();
    romsStore.recentRoms = [makeRom({ name: "old" })];
    romsStore.continuePlayingRoms = [makeRom({ name: "old" })];
    // Detailed-only fields have to survive a SimpleRom write.
    romsStore.currentRom = makeRom({ summary: "detailed" }) as DetailedRom;

    useRomSync().syncCachedRom(makeRom({ name: "new" }));

    expect(gallery.getRomAt(3)?.name).toBe("new");
    expect(romsStore.recentRoms[0].name).toBe("new");
    expect(romsStore.continuePlayingRoms[0].name).toBe("new");
    expect(romsStore.currentRom).toMatchObject({
      name: "new",
      summary: "detailed",
    });
  });

  it("syncCachedRom is a no-op for a ROM the gallery has never loaded", () => {
    const gallery = seedGallery(makeRom({ id: 2 }));

    useRomSync().syncCachedRom(makeRom({ id: 1 }));

    expect(gallery.byPosition.size).toBe(1);
    expect(gallery.getRomAt(3)?.id).toBe(2);
  });

  // The motivating case: a gallery showing games IGDB hasn't matched has to
  // drop a ROM the moment a match gives it an igdb_id.
  it("applyRomWrite refetches when the metadata-provider filter is active", () => {
    const gallery = seedGallery(makeRom());
    const galleryFilter = storeGalleryFilter();
    galleryFilter.selectedMetadataProviders = ["igdb"];
    galleryFilter.metadataProvidersLogic = "none";

    useRomSync().applyRomWrite(makeRom({ igdb_id: 1234 }));

    expect(gallery.byPosition.size).toBe(0);
    expect(getRoms).toHaveBeenCalled();
  });

  it("applyRomWrite refetches while the matched filter narrows the gallery", () => {
    const gallery = seedGallery(makeRom());
    storeGalleryFilter().filterMatched = false;

    useRomSync().applyRomWrite(makeRom({ igdb_id: 1234 }));

    expect(gallery.byPosition.size).toBe(0);
    expect(getRoms).toHaveBeenCalled();
  });

  it("applyRomWrite reorders an unfiltered gallery when the active sort key moved", () => {
    const gallery = seedGallery(makeRom({ name_sort_key: "chrono trigger" }));
    gallery.setOrderBy("name");

    useRomSync().applyRomWrite(makeRom({ name_sort_key: "zzz" }));

    expect(gallery.byPosition.size).toBe(0);
    expect(getRoms).toHaveBeenCalled();
  });

  it("applyRomWrite only checks the sort key in use", () => {
    const gallery = seedGallery(
      makeRom({ name_sort_key: "chrono trigger", fs_size_bytes: 100 }),
    );
    gallery.setOrderBy("fs_size_bytes");

    // The name moved, but the gallery is ordered by size, so nothing moves.
    useRomSync().applyRomWrite(
      makeRom({ name_sort_key: "zzz", fs_size_bytes: 100 }),
    );

    expect(gallery.byPosition.size).toBe(1);
    expect(getRoms).not.toHaveBeenCalled();
  });

  it("applyRomWrite keeps an unfiltered gallery when nothing it orders by moved", () => {
    const gallery = seedGallery(makeRom({ name_sort_key: "chrono trigger" }));
    gallery.setOrderBy("name");

    useRomSync().applyRomWrite(
      makeRom({ name_sort_key: "chrono trigger", summary: "edited" }),
    );

    expect(gallery.byPosition.size).toBe(1);
    expect(gallery.getRomAt(3)?.summary).toBe("edited");
    expect(getRoms).not.toHaveBeenCalled();
  });

  it("refreshAfterUserStateChange refetches the Favourites collection", () => {
    const gallery = seedGallery(makeRom());
    const collections = storeCollections();
    const favorites = { id: 9, name: "Favorites" } as unknown as Collection;
    collections.setFavoriteCollection(favorites);
    gallery.setCurrentCollection(favorites);

    useRomSync().refreshAfterUserStateChange();

    expect(gallery.byPosition.size).toBe(0);
    expect(getRoms).toHaveBeenCalled();
  });

  it("refreshAfterUserStateChange refetches while the status filter is active", () => {
    const gallery = seedGallery(makeRom());
    storeGalleryFilter().selectedStatuses = ["now_playing"];

    useRomSync().refreshAfterUserStateChange();

    expect(gallery.byPosition.size).toBe(0);
    expect(getRoms).toHaveBeenCalled();
  });

  // Narrower than applyRomWrite on purpose: hearting a game shouldn't throw
  // away a genre-filtered gallery, since a toggle can't change its genres.
  it("refreshAfterUserStateChange ignores filters that user state can't affect", () => {
    const gallery = seedGallery(makeRom());
    storeGalleryFilter().selectedGenres = ["RPG"];

    useRomSync().refreshAfterUserStateChange();

    expect(gallery.byPosition.size).toBe(1);
    expect(getRoms).not.toHaveBeenCalled();
  });

  // For writes that mutate the cached ROM in place, so `applyRomWrite` has no
  // before-state to diff: clearing last_played must still reorder a gallery
  // sorted by it.
  it("refreshIfOrderedBy refetches when the gallery orders by that field", () => {
    const gallery = seedGallery(makeRom());
    gallery.setOrderBy("last_played");

    useRomSync().refreshIfOrderedBy("last_played");

    expect(gallery.byPosition.size).toBe(0);
    expect(getRoms).toHaveBeenCalled();
  });

  it("refreshIfOrderedBy is a no-op under any other sort", () => {
    const gallery = seedGallery(makeRom());
    gallery.setOrderBy("name");

    useRomSync().refreshIfOrderedBy("last_played");

    expect(gallery.byPosition.size).toBe(1);
    expect(getRoms).not.toHaveBeenCalled();
  });

  // The three caches a removed ROM has to leave. Missing any one of them is
  // what #4151 and #4204 each had to fix, one call site at a time.
  it("removeCachedRoms drops the ROMs from the gallery, the v1 store and the selection", () => {
    const removed = makeRom({ id: 1 });
    const kept = makeRom({ id: 2 });
    const gallery = seedGallery(removed);
    const romsStore = storeRoms();
    romsStore._allRoms = [removed, kept];
    const selection = storeGallerySelection();
    selection.setSelection([removed, kept]);

    useRomSync().removeCachedRoms([removed]);

    expect(gallery.byPosition.size).toBe(0);
    expect(getRoms).toHaveBeenCalled();
    expect(romsStore._allRoms).toEqual([kept]);
    expect([...selection.selected.keys()]).toEqual([2]);
  });

  // Leaving a collection isn't leaving the library: the pruning that a real
  // delete needs stays in DeleteRomDialog rather than folding in here.
  it("removeCachedRoms leaves Home's rows alone", () => {
    const removed = makeRom({ id: 1 });
    seedGallery(removed);
    const romsStore = storeRoms();
    romsStore.recentRoms = [removed];
    romsStore.continuePlayingRoms = [removed];

    useRomSync().removeCachedRoms([removed]);

    expect(romsStore.recentRoms).toEqual([removed]);
    expect(romsStore.continuePlayingRoms).toEqual([removed]);
  });

  it("applyRomWrite leaves an unloaded ROM alone (no row on screen to reorder)", () => {
    const gallery = seedGallery(
      makeRom({ id: 2, name_sort_key: "earthbound" }),
    );
    gallery.setOrderBy("name");

    useRomSync().applyRomWrite(makeRom({ id: 1, name_sort_key: "zzz" }));

    expect(gallery.byPosition.size).toBe(1);
    expect(getRoms).not.toHaveBeenCalled();
  });
});
