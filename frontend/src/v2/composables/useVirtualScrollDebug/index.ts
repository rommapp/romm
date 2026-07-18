// useVirtualScrollDebug — shared diagnostics bridge from the active
// virtualised scroller to the DebugOverlay.
//
// Module-level singleton (mirrors the useDebugMode / useUiVersion pattern):
// the virtualised gallery publishes its window stats here on each scroll and
// the globally-mounted DebugOverlay reads them. `stats` is null whenever no
// virtual scroller is reporting (non-gallery routes, or debug mode off), so
// the overlay can simply `v-if` the block away.
//
// The point is to make windowing health observable: if virtualisation is
// working, `renderedRows` / `renderedCards` stay roughly constant
// (viewport + 2×overscan) as you scroll a huge library; if they climb with
// the scroll position, the window isn't being trimmed and that's the freeze.
import { ref } from "vue";

export interface VirtualScrollStats {
  /** Which scroller is reporting (e.g. "gallery·grid" / "gallery·list"). */
  label: string;
  /** Total virtual items (rows + headers) the scroller is managing. */
  total: number;
  /** Items currently mounted in the DOM (viewport + overscan both sides). */
  renderedRows: number;
  /** Cards/rows actually painted inside the rendered window — the real DOM
   *  weight (grid rows fan out into many cards). */
  renderedCards: number;
  /** Viewport-visible item range (inclusive). `last < first` ⇒ empty. */
  viewportFirst: number;
  viewportLast: number;
  /** Overscan count the scroller keeps on each side of the viewport. */
  overscan: number;
  /** Current scroll offset of the scroll container, in px. */
  scrollTop: number;
}

const stats = ref<VirtualScrollStats | null>(null);

export function useVirtualScrollDebug() {
  function publish(next: VirtualScrollStats) {
    stats.value = next;
  }
  function clear() {
    stats.value = null;
  }
  return { stats, publish, clear };
}
