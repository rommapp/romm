// Whole-result "select all" shared by the SelectionBar button, the
// list header checkbox and the shell's Ctrl/Cmd+A: loaded ROMs merge
// instantly, then the rest of the filtered result is fetched and
// merged. Surfaces with no rom id index stay loaded-only.
import { computed, toRaw } from "vue";
import { useI18n } from "vue-i18n";
import { useSnackbar } from "@/v2/composables/useSnackbar";
import storeGalleryRoms from "@/v2/stores/galleryRoms";
import storeGallerySelection from "@/v2/stores/gallerySelection";

type GallerySelectionState = "off" | "some" | "all";

export function useGallerySelectAll() {
  const galleryRoms = storeGalleryRoms();
  const selection = storeGallerySelection();
  const snackbar = useSnackbar();
  const { t } = useI18n();

  const selectingAll = computed(() => galleryRoms.selectingAll);

  /** True when every ROM of the filtered result is selected; picks
   * outside the current filter don't count against it. */
  const allSelected = computed<boolean>(() => {
    // Raw reads: the selection Map and the id index are only ever
    // replaced wholesale, so the property-level deps suffice and
    // per-entry tracking would allocate one dep per rom per scan.
    const selected = toRaw(selection.selected);
    const ids = galleryRoms.filteredRomIds;
    if (ids !== null) {
      if (ids.length === 0 || selection.count < ids.length) return false;
      return toRaw(ids).every((id) => selected.has(id));
    }
    // On the gallery the bootstrap is still pending: coverage unknown.
    if (galleryRoms.onGalleryView) return false;
    // Loaded-only surface: judge against what is loaded.
    const loaded = galleryRoms.byPosition;
    if (loaded.size === 0) return false;
    for (const rom of loaded.values()) {
      if (!selected.has(rom.id)) return false;
    }
    return true;
  });

  /** Tri-state for the list header checkbox glyph. */
  const selectionState = computed<GallerySelectionState>(() => {
    if (selection.count === 0) return "off";
    const ids = galleryRoms.filteredRomIds;
    // An empty result has nothing to select, whatever the count says.
    if ((ids ? ids.length : galleryRoms.byPosition.size) === 0) return "off";
    return allSelected.value ? "all" : "some";
  });

  /** Select the whole filtered result: loaded ROMs merge immediately,
   * the remainder merges when `fetchAllFilteredRoms` lands. A second
   * trigger supersedes the running fetch (the store aborts it). */
  async function selectAll(): Promise<void> {
    if (allSelected.value) return;
    selection.selectMany(galleryRoms.byPosition.values());
    if (allSelected.value) return;
    const ids = galleryRoms.filteredRomIds;
    // A known-empty result, or a loaded-only surface, has nothing to fetch.
    if (ids !== null && ids.length === 0) return;
    if (ids === null && !galleryRoms.onGalleryView) return;
    const epoch = selection.epoch;
    const before = new Set(toRaw(selection.selected).keys());
    try {
      const roms = await galleryRoms.fetchAllFilteredRoms();
      if (!roms || selection.epoch !== epoch) return;
      const selected = toRaw(selection.selected);
      // A ROM deselected while the fetch ran stays deselected.
      selection.selectMany(
        (function* () {
          for (const rom of roms) {
            if (before.has(rom.id) && !selected.has(rom.id)) continue;
            yield rom;
          }
        })(),
      );
    } catch (err) {
      console.error("[useGallerySelectAll] whole-result fetch failed", err);
      snackbar.error(t("gallery.selection-select-all-fail"));
    }
  }

  return { selectingAll, allSelected, selectionState, selectAll };
}
