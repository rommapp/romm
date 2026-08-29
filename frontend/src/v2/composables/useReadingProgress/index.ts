// useReadingProgress — persists and restores a document's per-user reading
// position for the current user. Works for any document-category rom file
// (manual or walkthrough): pass the scroll container ref and the composable
// restores the saved scroll fraction on load and saves it (debounced) as the
// user scrolls. Progress is a 0..1 scroll fraction stored server-side.
import { onBeforeUnmount, ref, watch, type Ref } from "vue";
import romApi from "@/services/api/rom";

const SAVE_DEBOUNCE_MS = 800;
// Below this fraction we treat the document as "not started" and skip saving
// noise from the initial layout settling.
const MIN_MEANINGFUL_PROGRESS = 0.02;

export function useReadingProgress(
  romId: Ref<number>,
  fileId: Ref<number | null>,
  scrollEl: Ref<HTMLElement | null>,
) {
  const progress = ref(0);
  const restoring = ref(false);
  let saveTimer: ReturnType<typeof setTimeout> | null = null;
  // The pending save carries the document it was measured against, so a flush
  // triggered after the viewer switched files still targets the right one.
  let pending: { romId: number; fileId: number; value: number } | null = null;

  function fraction(el: HTMLElement): number {
    const scrollable = el.scrollHeight - el.clientHeight;
    if (scrollable <= 0) return 0;
    return Math.min(1, Math.max(0, el.scrollTop / scrollable));
  }

  async function restore() {
    if (fileId.value == null) return;
    try {
      const { data } = await romApi.getFileProgress({
        romId: romId.value,
        fileId: fileId.value,
      });
      progress.value = data.progress ?? 0;
      const el = scrollEl.value;
      if (el && progress.value > MIN_MEANINGFUL_PROGRESS) {
        restoring.value = true;
        const scrollable = el.scrollHeight - el.clientHeight;
        el.scrollTop = progress.value * scrollable;
        // Let the scroll event from this programmatic set pass without
        // scheduling a redundant save.
        requestAnimationFrame(() => {
          restoring.value = false;
        });
      }
    } catch (err) {
      console.error("Failed to restore reading progress", err);
    }
  }

  function flush() {
    const save = pending;
    pending = null;
    if (!save) return;
    romApi
      .updateFileProgress({
        romId: save.romId,
        fileId: save.fileId,
        data: { progress: save.value, finished: save.value >= 0.99 },
      })
      .catch((err) => console.error("Failed to save reading progress", err));
  }

  function cancelPendingSave() {
    if (saveTimer) {
      clearTimeout(saveTimer);
      saveTimer = null;
    }
  }

  function onScroll() {
    const el = scrollEl.value;
    if (!el || restoring.value || fileId.value == null) return;
    const value = fraction(el);
    pending = { romId: romId.value, fileId: fileId.value, value };
    progress.value = value;
    cancelPendingSave();
    saveTimer = setTimeout(flush, SAVE_DEBOUNCE_MS);
  }

  // Re-restore whenever the tracked file changes (viewer reused across docs).
  watch(fileId, () => {
    cancelPendingSave();
    // Commit the outgoing document's position before following the new one.
    flush();
    progress.value = 0;
    void restore();
  });

  onBeforeUnmount(() => {
    cancelPendingSave();
    flush();
  });

  return { progress, restore, onScroll };
}
