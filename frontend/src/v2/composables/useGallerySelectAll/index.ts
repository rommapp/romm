// Whole-result "select all" shared by the SelectionBar button, the
// list header checkbox and the shell's Ctrl/Cmd+A: loaded ROMs merge
// instantly, then the rest of the filtered result is fetched and
// merged. Surfaces with no rom id index after bootstrap stay loaded-only.
import { computed, ref, toRaw } from "vue";
import { useI18n } from "vue-i18n";
import { useSnackbar } from "@/v2/composables/useSnackbar";
import storeGalleryRoms from "@/v2/stores/galleryRoms";
import storeGallerySelection from "@/v2/stores/gallerySelection";

export type GallerySelectionState = "off" | "some" | "all";

// Module-level so every call site shares one in-flight flag: a second
// trigger while a fetch runs is a no-op, not a second fetch.
const selectingAll = ref(false);
// Selection epoch the in-flight fetch may merge against. Re-armed by
// every trigger, so a select-all after a clear reuses the running fetch.
let pendingEpoch = 0;
// Ids selected when the last trigger fired: a ROM deselected while the
// fetch runs stays deselected when the late result merges.
let selectedAtDispatch = new Set<number>();

export function useGallerySelectAll() {
  const galleryRoms = storeGalleryRoms();
  const selection = storeGallerySelection();
  const snackbar = useSnackbar();
  const { t } = useI18n();

  /** True when every ROM of the filtered result is selected; picks
   * outside the current filter don't count against it. */
  const allSelected = computed<boolean>(() => {
    // Raw reads: the selection Map and the id index are only ever
    // replaced wholesale, so the property-level deps suffice and
    // per-entry tracking would allocate one dep per rom per scan.
    const selected = toRaw(selection.selected);
    const ids = toRaw(galleryRoms.romIdIndex);
    if (ids.length > 0) {
      if (selection.count < ids.length) return false;
      return ids.every((id) => selected.has(id));
    }
    // No index while the bootstrap is pending: coverage is unknown, so
    // report not-all and let `selectAll` fetch the whole result.
    if (!galleryRoms.metadataLoaded) return false;
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
    // An empty result has nothing to select, whatever the count says.
    if (
      galleryRoms.romIdIndex.length === 0 &&
      galleryRoms.byPosition.size === 0
    ) {
      return "off";
    }
    return allSelected.value ? "all" : "some";
  });

  /** Select the whole filtered result: loaded ROMs merge immediately,
   * the remainder merges when `fetchAllFilteredRoms` lands. */
  async function selectAll(): Promise<void> {
    if (galleryRoms.byPosition.size > 0) {
      selection.selectMany(galleryRoms.byPosition.values());
    }
    pendingEpoch = selection.epoch;
    selectedAtDispatch = new Set(selection.ids);
    if (selectingAll.value || allSelected.value) return;
    // The fetch needs a gallery context to scope the query; without one
    // (Settings "Missing" tab, a mid-switch reset) stay loaded-only.
    if (!galleryRoms.onGalleryView) return;
    // An id index still empty after bootstrap means the surface opted
    // out of it, or the result is empty: nothing more to fetch.
    if (galleryRoms.metadataLoaded && galleryRoms.romIdIndex.length === 0) {
      return;
    }
    selectingAll.value = true;
    try {
      const roms = await galleryRoms.fetchAllFilteredRoms();
      if (roms && selection.epoch === pendingEpoch) {
        const selected = toRaw(selection.selected);
        selection.selectMany(
          roms.filter(
            (rom) => !selectedAtDispatch.has(rom.id) || selected.has(rom.id),
          ),
        );
      }
    } catch (err) {
      console.error("[useGallerySelectAll] whole-result fetch failed", err);
      snackbar.error(t("gallery.selection-select-all-fail"));
    } finally {
      selectingAll.value = false;
    }
  }

  return { selectingAll, allSelected, selectionState, selectAll };
}
