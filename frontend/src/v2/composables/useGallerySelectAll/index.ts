// useGallerySelectAll: whole-result "select all" shared by the
// SelectionBar button, the list header checkbox and the shell's
// Ctrl/Cmd+A. It selects the entire filtered result, not just the
// loaded windows: loaded ROMs apply instantly, then the rest of the
// result set is fetched (the selection store keeps full SimpleRoms so
// bulk actions keep working) and merged when it lands.
//
// Coverage is judged against `romIdIndex`, the full ordered id list of
// the current filtered result that the gallery bootstrap already
// fetches for virtual scrolling. Surfaces that opt out of that sidecar
// (Settings "Missing" tab) fall back to loaded-only coverage, where the
// instant merge already satisfies `allSelected` and no fetch happens.
import { computed, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useSnackbar } from "@/v2/composables/useSnackbar";
import storeGalleryRoms from "@/v2/stores/galleryRoms";
import storeGallerySelection from "@/v2/stores/gallerySelection";

export type GallerySelectionState = "off" | "some" | "all";

// Module-level so every call site shares one in-flight flag: a second
// trigger while a fetch runs is a no-op, not a second fetch.
const selectingAll = ref(false);

export function useGallerySelectAll() {
  const galleryRoms = storeGalleryRoms();
  const selection = storeGallerySelection();
  const snackbar = useSnackbar();
  const { t } = useI18n();

  /** True when every ROM of the filtered result is selected. Selected
   * ROMs outside the current filter (kept across an in-view filter
   * change) don't count against it. */
  const allSelected = computed<boolean>(() => {
    const ids = galleryRoms.romIdIndex;
    if (ids.length > 0) {
      return ids.every((id) => selection.selected.has(id));
    }
    const loaded = galleryRoms.byPosition;
    if (loaded.size === 0) return false;
    for (const rom of loaded.values()) {
      if (!selection.selected.has(rom.id)) return false;
    }
    return true;
  });

  /** Tri-state for the list header checkbox glyph. */
  const selectionState = computed<GallerySelectionState>(() => {
    if (selection.count === 0) return "off";
    return allSelected.value ? "all" : "some";
  });

  /** Select the whole filtered result. Loaded ROMs merge immediately;
   * the remainder arrives from `fetchAllFilteredRoms` and merges unless
   * the user cleared the selection in the meantime (epoch guard). */
  async function selectAll(): Promise<void> {
    selection.selectMany(galleryRoms.byPosition.values());
    if (selectingAll.value || allSelected.value) return;
    const epochAtStart = selection.epoch;
    selectingAll.value = true;
    try {
      const roms = await galleryRoms.fetchAllFilteredRoms();
      if (roms && selection.epoch === epochAtStart) {
        selection.selectMany(roms);
      }
    } catch {
      snackbar.error(t("gallery.selection-select-all-fail"));
    } finally {
      selectingAll.value = false;
    }
  }

  return { selectingAll, allSelected, selectionState, selectAll };
}
