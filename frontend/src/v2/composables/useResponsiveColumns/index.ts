// useResponsiveColumns — measures the bound element via ResizeObserver and
// returns a reactive column count derived from `floor((w + gap) / (card + gap))`.
//
// Used by gallery views to chunk a flat ROM list into rows for the
// virtualiser. The breakpoint logic mirrors the existing CSS grid
// (`grid-template-columns: repeat(auto-fill, var(--r-card-art-w))`) so the
// virtual rows visually match what the non-virtualised CSS grid would draw.
import {
  onBeforeUnmount,
  onMounted,
  ref,
  watch,
  type Ref,
  type ShallowRef,
} from "vue";

interface Options {
  /** Width of one card in px (default matches `--r-card-art-w` = 158). */
  cardWidth?: number;
  /** Horizontal gap between cards in px (default 12 — matches `gap: 18px 12px`). */
  gap?: number;
  /** Minimum column count (default 1). */
  min?: number;
  /** Pixels to subtract from the observed width before computing columns
   * (e.g., the container's left+right padding, or sibling chrome that
   * shares the bounding rect). Default 0. */
  inset?: number;
}

export function useResponsiveColumns(
  containerRef: Ref<HTMLElement | null> | ShallowRef<HTMLElement | null>,
  options: Options = {},
) {
  const cardWidth = options.cardWidth ?? 158;
  const gap = options.gap ?? 12;
  const min = options.min ?? 1;
  const inset = options.inset ?? 0;

  const columns = ref<number>(min);
  let observer: ResizeObserver | null = null;

  function compute(width: number) {
    const usable = width - inset;
    if (usable <= 0) return;
    // CSS auto-fill semantics: floor((containerWidth + gap) / (cardWidth + gap))
    const next = Math.max(min, Math.floor((usable + gap) / (cardWidth + gap)));
    if (next !== columns.value) columns.value = next;
  }

  function attach(el: HTMLElement) {
    compute(el.clientWidth);
    observer = new ResizeObserver((entries) => {
      for (const entry of entries) compute(entry.contentRect.width);
    });
    observer.observe(el);
  }

  function detach() {
    observer?.disconnect();
    observer = null;
  }

  onMounted(() => {
    if (containerRef.value) attach(containerRef.value);
  });

  // Re-attach if the bound ref swaps (rare, but safe).
  watch(containerRef, (next, prev) => {
    if (prev) detach();
    if (next) attach(next);
  });

  onBeforeUnmount(detach);

  return { columns };
}
