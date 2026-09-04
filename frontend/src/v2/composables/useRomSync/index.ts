// useRomSync: fan a ROM mutation out to every cache that holds it.
//
// The same ROM is cached in two stores: `galleryRoms.byPosition` (the
// gallery's sparse windowed cache) and `stores/roms`, which owns Home's
// recent / continue-playing rows and the `currentRom` behind GameDetails.
//
// Optimistic toggles appeared to work without this only by accident: they
// mutate the ROM object in place and the gallery holds that same object
// reference. Anything that replaces the object with a fresh one from the
// API response (edit, match, asset upload) needs an explicit sync.
import romApi from "@/services/api/rom";
import storeCollections from "@/stores/collections";
import storeGalleryFilter from "@/stores/galleryFilter";
import storeRoms, { type DetailedRom, type SimpleRom } from "@/stores/roms";
import storeGalleryRoms, {
  type GalleryOrderKey,
} from "@/v2/stores/galleryRoms";
import storeGallerySelection from "@/v2/stores/gallerySelection";

/** The value the gallery is ordered by, per sort key. Declared as a full
 * `Record` so a new `GalleryOrderKey` fails to compile until it's handled
 * here. `name` resolves to `name_sort_key` because that's the column the
 * backend actually orders on. */
const SORT_VALUE: Record<GalleryOrderKey, (rom: SimpleRom) => unknown> = {
  name: (rom) => rom.name_sort_key,
  fs_name: (rom) => rom.fs_name,
  platform_id: (rom) => rom.platform_id,
  fs_size_bytes: (rom) => rom.fs_size_bytes,
  created_at: (rom) => rom.created_at,
  updated_at: (rom) => rom.updated_at,
  first_release_date: (rom) => rom.metadatum?.first_release_date,
  average_rating: (rom) => rom.metadatum?.average_rating,
  last_played: (rom) => rom.rom_user?.last_played,
};

const replaceById = (roms: SimpleRom[], rom: SimpleRom) =>
  roms.map((cached) => (cached.id === rom.id ? rom : cached));

export function useRomSync() {
  const romsStore = storeRoms();
  const galleryRomsStore = storeGalleryRoms();
  const galleryFilter = storeGalleryFilter();
  const collectionsStore = storeCollections();
  const gallerySelection = storeGallerySelection();

  /** Apply an already-persisted ROM to every cache that renders it; this
   * writes nothing to the server. Safe to call with a ROM none of them
   * hold: each update is a no-op when no surface has that id. */
  function syncCachedRom(rom: SimpleRom) {
    galleryRomsStore.update(rom);
    romsStore.recentRoms = replaceById(romsStore.recentRoms, rom);
    romsStore.continuePlayingRoms = replaceById(
      romsStore.continuePlayingRoms,
      rom,
    );
    // Spread over the cached DetailedRom so its detailed-only fields
    // (metadatum, screenshots, related games, ...) survive a SimpleRom write.
    if (romsStore.currentRom?.id === rom.id) {
      romsStore.currentRom = { ...romsStore.currentRom, ...rom };
    }
  }

  /** Re-read a ROM from the API and apply it everywhere it is cached, for the
   * surfaces that need the detailed record back rather than the row their
   * write returned.
   *
   * `syncCachedRom` owns the `currentRom` write, so a response that lands
   * after the user opened another game leaves the open ROM alone. */
  async function refetchRom(romId: number): Promise<DetailedRom | null> {
    try {
      const { data } = await romApi.getRom({ romId });
      syncCachedRom(data);
      return data;
    } catch (error) {
      console.error(error);
      return null;
    }
  }

  /** Drop ROMs that have left the current view from every cache holding
   * them: the gallery's windowed cache, the v1 store, and the selection.
   * Missing any one of the three leaves the cards on screen.
   *
   * Says nothing about *why* they left. Callers that remove a ROM from a
   * view (a bulk unfavourite, a collection removal) and callers that delete
   * it outright both need these three, but only the latter should also
   * prune Home's recent / continue-playing rows: a game taken out of a
   * collection still belongs in Continue Playing. That pruning stays with
   * the caller that means it. */
  function removeCachedRoms(roms: SimpleRom[]) {
    gallerySelection.removeIds(roms.map((rom) => rom.id));
    romsStore.remove(roms);
    galleryRomsStore.remove(roms);
  }

  /** Did this write move the value the gallery is currently ordered by?
   * `previous` is null when the ROM isn't in any loaded window, in which
   * case there's no row on screen to reorder. */
  function sortValueChanged(previous: SimpleRom | null, next: SimpleRom) {
    if (!previous) return false;
    const resolve = SORT_VALUE[galleryRomsStore.orderBy];
    return resolve(previous) !== resolve(next);
  }

  /** Sync a deliberate metadata write (the edit / match dialogs) and refetch
   * the gallery when an in-place swap would leave it lying.
   *
   * Two things a swap can't fix. Membership: matching a ROM while the gallery
   * shows "not matched in IGDB" has to remove it, and only the backend can
   * say what the new result set is, so any active filter forces a refetch
   * rather than us guessing which filters a match moved (it rewrites provider
   * ids, name, and the genre / company / tag metadata behind half the
   * drawer). Order: a rename under name-ascending has to move the card, so
   * compare just the active sort key and leave the gallery alone when it
   * didn't move.
   *
   * Use `syncCachedRom` instead for optimistic toggles and asset writes:
   * throwing the windows away costs skeletons and the scroll position, too
   * much for a favourite flip or a screenshot upload. */
  function applyRomWrite(rom: SimpleRom) {
    // Read the pre-write copy before `syncCachedRom` overwrites it.
    const previous = galleryRomsStore.getRomById(rom.id);
    syncCachedRom(rom);
    // Only the server knows which virtual collections this write moved the ROM
    // between.
    void collectionsStore.refreshVirtualCollections();
    if (!galleryRomsStore.onGalleryView) return;
    if (!galleryFilter.isFiltered() && !sortValueChanged(previous, rom)) return;
    galleryRomsStore.invalidateWindows();
    void galleryRomsStore.fetchInitialMetadata();
  }

  /** Refetch after a favourite or playing-status write, for the surfaces
   * whose membership depends on it: the Favourites collection, the
   * favourites filter, and the status filter. Un-hearting a game while
   * viewing Favourites has to remove the card, not just un-fill the icon.
   *
   * Narrow on purpose, unlike `applyRomWrite`. A metadata write rewrites
   * enough of a ROM that any active filter is suspect, but a toggle only
   * touches `rom_user` and collection membership. Checking `isFiltered()`
   * here would reset a genre-filtered gallery every time someone hearts
   * something, and these toggles are cheap and frequent.
   *
   * Call once per user action, after the writes settle: the bulk bar
   * applies a status across a whole selection, and reconciling per ROM
   * would invalidate the windows N times over. */
  function refreshAfterUserStateChange() {
    if (!galleryRomsStore.onGalleryView) return;
    const favoriteId = collectionsStore.favoriteCollection?.id;
    const onFavorites =
      favoriteId !== undefined &&
      galleryRomsStore.currentCollection?.id === favoriteId;
    if (
      !onFavorites &&
      galleryFilter.filterFavorites === null &&
      galleryFilter.selectedStatuses.length === 0
    ) {
      return;
    }
    galleryRomsStore.invalidateWindows();
    void galleryRomsStore.fetchInitialMetadata();
  }

  /** Refetch when a write changed the field the gallery is ordered by, for
   * callers that can't use `applyRomWrite`'s before/after comparison because
   * they mutate the cached ROM in place (which leaves nothing to compare
   * against). The caller names the field it wrote. */
  function refreshIfOrderedBy(key: GalleryOrderKey) {
    if (!galleryRomsStore.onGalleryView) return;
    if (galleryRomsStore.orderBy !== key) return;
    galleryRomsStore.invalidateWindows();
    void galleryRomsStore.fetchInitialMetadata();
  }

  return {
    syncCachedRom,
    refetchRom,
    removeCachedRoms,
    applyRomWrite,
    refreshAfterUserStateChange,
    refreshIfOrderedBy,
  };
}
