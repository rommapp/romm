// useRomSync: fan a ROM mutation out to every cache that holds it.
//
// Two stores cache the same ROM for different surfaces: v1 `stores/roms`
// (Home rows, `recentRoms`, `currentRom`) and v2 `galleryRoms.byPosition`
// (the gallery's sparse windowed cache). The v2 gallery never reads v1's
// `_allRoms`, so a write that only lands in v1 leaves the gallery card
// rendering the pre-edit name and cover until its window happens to be
// refetched.
//
// Optimistic toggles appeared to work without this only by accident: they
// mutate the ROM object in place and the gallery holds that same object
// reference. Anything that replaces the object with a fresh one from the
// API response (edit, match, asset upload) needs an explicit sync.
import storeCollections from "@/stores/collections";
import storeGalleryFilter from "@/stores/galleryFilter";
import storeRoms, { type SimpleRom } from "@/stores/roms";
import storeGalleryRoms, {
  type GalleryOrderKey,
} from "@/v2/stores/galleryRoms";

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

export function useRomSync() {
  const romsStore = storeRoms();
  const galleryRomsStore = storeGalleryRoms();
  const galleryFilter = storeGalleryFilter();
  const collectionsStore = storeCollections();

  /** Apply an updated ROM to every cache holding it. Safe to call with a
   * ROM the gallery has never loaded: the gallery update is a no-op when
   * no position holds that id. */
  function syncRom(rom: SimpleRom) {
    romsStore.update(rom);
    galleryRomsStore.update(rom);
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
   * Use `syncRom` instead for optimistic toggles and asset writes: throwing
   * the windows away costs skeletons and the scroll position, too much for a
   * favourite flip or a screenshot upload. */
  function applyRomWrite(rom: SimpleRom) {
    // Read the pre-write copy before `syncRom` overwrites it.
    const previous = galleryRomsStore.getRomById(rom.id);
    syncRom(rom);
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
    syncRom,
    applyRomWrite,
    refreshAfterUserStateChange,
    refreshIfOrderedBy,
  };
}
