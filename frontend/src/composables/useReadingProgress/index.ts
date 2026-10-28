// useReadingProgress: tracks how far through a document the reader is, and
// persists that position per user. Works for any document-category rom file
// (manual or walkthrough), in both flavours:
//
//   * Scrolled documents (text, HTML, Markdown) report via `onScroll`, and the
//     composable restores the saved scroll fraction onto `scrollEl`.
//   * Paginated documents (PDF) report via `setPage`, which also stores the
//     page so restoring lands on it exactly.
//
// `progress` is a 0..1 fraction and always reflects the live position, so a
// document with no rom file behind it (the scraped primary manual) still
// drives a progress bar; only the saving half needs a file id.
import { useResizeObserver, useTimeoutFn } from "@vueuse/core";
import { onBeforeUnmount, ref, watch, type Ref } from "vue";
import romApi from "@/services/api/rom";

const SAVE_DEBOUNCE_MS = 800;
// Below this fraction we treat the document as "not started" and skip saving
// noise from the initial layout settling.
const MIN_MEANINGFUL_PROGRESS = 0.02;

type SavedPosition = { progress: number; lastPage: number | null };

export function useReadingProgress(
  romId: Ref<number>,
  fileId: Ref<number | null>,
  scrollEl?: Ref<HTMLElement | null>,
) {
  const progress = ref(0);
  const restoring = ref(false);
  // The pending save carries the document it was measured against, so a flush
  // triggered after the viewer switched files still targets the right one.
  let pending: {
    romId: number;
    fileId: number;
    progress: number;
    lastPage: number | null;
  } | null = null;

  function fraction(el: HTMLElement): number {
    const scrollable = el.scrollHeight - el.clientHeight;
    if (scrollable <= 0) return 0;
    return Math.min(1, Math.max(0, el.scrollTop / scrollable));
  }

  // Subtabs mount their viewers up front and hide the inactive ones, so a
  // restore often lands on a container that has no height yet. Hold the
  // position and apply it once the panel is actually laid out.
  const deferredScroll = ref<number | null>(null);
  useResizeObserver(
    () => (deferredScroll.value == null ? null : scrollEl?.value),
    () => {
      const el = scrollEl?.value;
      const held = deferredScroll.value;
      if (!el || held == null) return;
      if (el.scrollHeight - el.clientHeight <= 0) return;
      deferredScroll.value = null;
      applyScroll(held);
    },
  );

  function applyScroll(value: number) {
    const el = scrollEl?.value;
    if (!el) return;
    const scrollable = el.scrollHeight - el.clientHeight;
    if (scrollable <= 0) {
      deferredScroll.value = value;
      return;
    }
    restoring.value = true;
    el.scrollTop = value * scrollable;
    // Let the scroll event from this programmatic set pass without scheduling
    // a redundant save.
    requestAnimationFrame(() => {
      restoring.value = false;
    });
  }

  async function restore(): Promise<SavedPosition> {
    const empty: SavedPosition = { progress: 0, lastPage: null };
    if (fileId.value == null) return empty;
    try {
      const { data } = await romApi.getFileProgress({
        romId: romId.value,
        fileId: fileId.value,
      });
      const saved: SavedPosition = {
        progress: data.progress ?? 0,
        lastPage: data.last_page ?? null,
      };
      progress.value = saved.progress;
      if (saved.progress > MIN_MEANINGFUL_PROGRESS) applyScroll(saved.progress);
      return saved;
    } catch (err) {
      console.error("Failed to restore reading progress", err);
      return empty;
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
        data: {
          progress: save.progress,
          last_page: save.lastPage,
          finished: save.progress >= 0.99,
        },
      })
      .catch((err) => console.error("Failed to save reading progress", err));
  }

  const { start: scheduleSave, stop: cancelPendingSave } = useTimeoutFn(
    flush,
    SAVE_DEBOUNCE_MS,
    { immediate: false },
  );

  function schedule(lastPage: number | null) {
    if (fileId.value == null) return;
    pending = {
      romId: romId.value,
      fileId: fileId.value,
      progress: progress.value,
      lastPage,
    };
    scheduleSave();
  }

  function onScroll() {
    const el = scrollEl?.value;
    if (!el || restoring.value) return;
    progress.value = fraction(el);
    schedule(null);
  }

  /** Report the position of a paginated document, 1-based. */
  function setPage(page: number, totalPages: number) {
    if (restoring.value || totalPages <= 0) return;
    progress.value = Math.min(1, Math.max(0, page / totalPages));
    schedule(page);
  }

  /** Suppress saves while a programmatic jump settles (PDF page restore). */
  function suppressWhileRestoring() {
    restoring.value = true;
    requestAnimationFrame(() => {
      restoring.value = false;
    });
  }

  // Re-restore whenever the tracked file changes (viewer reused across docs).
  watch(fileId, () => {
    cancelPendingSave();
    // Commit the outgoing document's position before following the new one.
    flush();
    deferredScroll.value = null;
    progress.value = 0;
    void restore();
  });

  onBeforeUnmount(() => {
    cancelPendingSave();
    flush();
  });

  return { progress, restore, onScroll, setPage, suppressWhileRestoring };
}
