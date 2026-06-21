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

/** A value that may be a constant or a reactive getter. Getters let the
 *  caller vary card width / inset by breakpoint and have the column count
 *  recompute automatically (e.g. smaller cards + tighter gutters on xs). */
type Dynamic = number | (() => number);

function resolve(v: Dynamic | undefined, dflt: number): number {
  if (v === undefined) return dflt;
  return typeof v === "function" ? v() : v;
}

interface Options {
  /** Width of one card in px (default matches `--r-card-art-w` = 158).
   *  May be a getter for responsive sizing. */
  cardWidth?: Dynamic;
  /** Horizontal gap between cards in px (default 12). */
  gap?: Dynamic;
  /** Minimum column count (default 1). */
  min?: number;
  /** Pixels to subtract from the observed width before computing columns
   * (e.g., the container's left+right padding, or sibling chrome that
   * shares the bounding rect). Default 0. May be a getter. */
  inset?: Dynamic;
}

export function useResponsiveColumns(
  containerRef: Ref<HTMLElement | null> | ShallowRef<HTMLElement | null>,
  options: Options = {},
) {
  const min = options.min ?? 1;

  const columns = ref<number>(min);
  // Observed content width minus `inset` — the px available to a row of
  // cards. Exposed for consumers that flow-pack by width (the gallery's
  // wrapping rows) rather than chunk by a fixed column count.
  const usableWidth = ref<number>(0);
  let observer: ResizeObserver | null = null;
  // Last observed width — kept so a change in a reactive option (card
  // width / inset flipping at a breakpoint) can recompute without waiting
  // for the next resize event.
  let lastWidth = 0;

  function compute(width: number) {
    lastWidth = width;
    const cardWidth = resolve(options.cardWidth, 158);
    const gap = resolve(options.gap, 12);
    const inset = resolve(options.inset, 0);
    const usable = width - inset;
    if (usable <= 0) return;
    if (usable !== usableWidth.value) usableWidth.value = usable;
    // CSS auto-fill semantics: floor((containerWidth + gap) / (cardWidth + gap))
    const next = Math.max(min, Math.floor((usable + gap) / (cardWidth + gap)));
    if (next !== columns.value) columns.value = next;
  }

  // Recompute when a reactive option changes (breakpoint flip) using the
  // last observed width. Tracks the getters by evaluating them here.
  watch(
    () => [
      resolve(options.cardWidth, 158),
      resolve(options.gap, 12),
      resolve(options.inset, 0),
    ],
    () => {
      if (lastWidth > 0) compute(lastWidth);
    },
  );

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

  return { columns, usableWidth };
}
