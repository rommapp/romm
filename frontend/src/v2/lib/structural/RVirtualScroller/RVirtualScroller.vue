<script setup lang="ts">
// RVirtualScroller — custom windowed list with exact-offset positioning.
//
// We own the math: heights are reported by the consumer per item (via
// `getItemHeight`), the prefix-sum offset table is built once per items
// change, and `scrollToIndex` is `containerEl.scrollTop = ...` — no
// estimation, no drift, lands exactly on target items.
//
// Two ranges are exposed:
//   * `renderedRange` = items in the DOM = viewport ± overscan. Drives
//     the slot rendering.
//   * `viewportRange` = items whose pixel rect actually intersects the
//     visible viewport. Drives consumers that care about "what the user
//     is looking at right now" — AlphaStrip highlight, dwell-debounced
//     prefetch, etc.
//
// Two extension slots sit alongside the virtualised list inside the
// scrolling container so they share its scrollbar:
//
//   * `#prepend` — flow content rendered ABOVE the virtualised inner.
//                  Use this for headers / hero panels that should
//                  scroll naturally with the rest of the content.
//   * `#sticky`  — flow content rendered BETWEEN `#prepend` and the
//                  virtualised inner, with `position: sticky; top: 0`.
//                  Use this for a toolbar that should pin once the
//                  user scrolls past the prepend block. Native sticky
//                  runs on the compositor — zero JS scroll lag, no
//                  per-frame transform tracking needed.
//
// `scrollToIndex(idx, { stickyOffset })` accounts for the prepend and
// sticky bands automatically (the inner's `offsetTop` is in the math).
// Pass the sticky band's height as `stickyOffset` so the target item
// lands just below the pinned sticky element instead of behind it.
//
// Performance contract:
//   * Rendered items are absolutely positioned via `transform: translateY`.
//     The container has `height: <total>px` so the native scrollbar
//     reflects total content, but only ~viewport+overscan items live in
//     the DOM at any time.
//   * Computeds re-evaluate only on scrollTop / containerHeight / items
//     changes. Binary searches make per-scroll work O(log n).
import { computed, onMounted, onUnmounted, ref, watch } from "vue";

defineOptions({ inheritAttrs: false });

interface Props {
  /** Array of items to virtualise. The slot receives `{ item, index }`. */
  items: readonly unknown[];
  /** Returns the item's height in pixels. Called once per item per
   * structural change (items array swap or items.length change). Heights
   * are cached in an offset table; if a height value depends on dynamic
   * state, bump items by reference to force a recompute. */
  getItemHeight: (item: unknown, index: number) => number;
  /** Items kept rendered above/below the visible viewport for smooth
   * scrolling. Default 25 → ~50 extra rendered + visible. */
  overscan?: number;
  /** Viewport height. Number = px, string = any CSS length, undefined =
   * fill parent (the wrapper element gets `height: 100%`). */
  height?: number | string;
}

const props = withDefaults(defineProps<Props>(), {
  overscan: 25,
  height: undefined,
});

const emit = defineEmits<{
  /** Fires whenever the viewport-visible range changes (after scroll
   * settles, on resize, on items change). The payload's `last` is
   * exclusive-of: a range with `first === last` means zero items. */
  (e: "update:viewportRange", range: { first: number; last: number }): void;
}>();

defineSlots<{
  default(props: { item: unknown; index: number }): unknown;
  /** Flow content above the virtualised inner — scrolls with the list. */
  prepend(): unknown;
  /** Flow content between `#prepend` and the inner, position: sticky. */
  sticky(): unknown;
}>();

const containerEl = ref<HTMLElement | null>(null);
const innerEl = ref<HTMLElement | null>(null);
const scrollTop = ref(0);
const containerHeight = ref(0);

// Offset table: offsets[i] = top-y of item i. offsets[N] = totalHeight.
// Size N+1 so we can answer "bottom of item i" as offsets[i+1].
const offsets = computed<number[]>(() => {
  const len = props.items.length;
  const out = new Array<number>(len + 1);
  out[0] = 0;
  for (let i = 0; i < len; i++) {
    const h = props.getItemHeight(props.items[i], i);
    out[i + 1] = out[i] + (Number.isFinite(h) && h > 0 ? h : 0);
  }
  return out;
});

const totalHeight = computed(() => {
  const offs = offsets.value;
  return offs[offs.length - 1] ?? 0;
});

// `innerOffsetTop` — distance from the scroller's content top to the
// virtualised inner's top edge. Captures any space taken by the
// `#prepend` and `#sticky` slots above the inner. Tracked via a
// ResizeObserver and a one-shot read on each scroll so AlphaStrip /
// `scrollToIndex` math stays correct as the prepend's height changes
// (e.g. the platform InfoPanel reflowing on viewport resize).
const innerOffsetTop = ref(0);

function findFirstVisible(offs: number[], top: number): number {
  let lo = 0;
  let hi = offs.length - 2;
  if (hi < 0) return 0;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (offs[mid + 1] > top) hi = mid;
    else lo = mid + 1;
  }
  return lo;
}

function findLastVisible(offs: number[], bottom: number): number {
  let lo = 0;
  let hi = offs.length - 2;
  if (hi < 0) return -1;
  while (lo < hi) {
    const mid = (lo + hi + 1) >> 1; // bias up to terminate
    if (offs[mid] < bottom) lo = mid;
    else hi = mid - 1;
  }
  return lo;
}

const viewportRange = computed<{ first: number; last: number }>(() => {
  const len = props.items.length;
  if (len === 0 || containerHeight.value === 0) {
    return { first: 0, last: -1 };
  }
  // The viewport, in inner-relative coordinates: subtract whatever
  // space the prepend / sticky bands take above the inner.
  const top = Math.max(0, scrollTop.value - innerOffsetTop.value);
  const bottom = top + containerHeight.value;
  const first = findFirstVisible(offsets.value, top);
  const last = findLastVisible(offsets.value, bottom);
  return { first, last };
});

const renderedRange = computed<{ first: number; last: number }>(() => {
  const len = props.items.length;
  if (len === 0) return { first: 0, last: -1 };
  const v = viewportRange.value;
  if (v.last < v.first) return { first: 0, last: -1 };
  const overscan = Math.max(0, props.overscan);
  return {
    first: Math.max(0, v.first - overscan),
    last: Math.min(len - 1, v.last + overscan),
  };
});

interface RenderedEntry {
  item: unknown;
  index: number;
  top: number;
}

const renderedItems = computed<RenderedEntry[]>(() => {
  const r = renderedRange.value;
  if (r.last < r.first) return [];
  const offs = offsets.value;
  const items = props.items;
  const out: RenderedEntry[] = [];
  for (let i = r.first; i <= r.last; i++) {
    out.push({ item: items[i], index: i, top: offs[i] });
  }
  return out;
});

// Scroll handling — passive listener; reads scrollTop and lets Vue's
// reactivity batch downstream computeds into the next microtask.
function onScroll(e: Event) {
  scrollTop.value = (e.target as HTMLElement).scrollTop;
}

// Container size + inner offset tracking.
let containerObserver: ResizeObserver | null = null;
let innerObserver: ResizeObserver | null = null;

function syncInnerOffset() {
  const inner = innerEl.value;
  if (!inner) return;
  innerOffsetTop.value = inner.offsetTop;
}

onMounted(() => {
  const container = containerEl.value;
  if (!container) return;
  containerHeight.value = container.clientHeight;
  scrollTop.value = container.scrollTop;
  syncInnerOffset();

  containerObserver = new ResizeObserver(() => {
    containerHeight.value = container.clientHeight;
    syncInnerOffset();
  });
  containerObserver.observe(container);

  // Watch the prepend / sticky bands so their height changes (e.g.
  // header reflow on resize) propagate into `innerOffsetTop`. We
  // observe the container itself; any layout shift in its descendants
  // bubbles up via the container's own size or the inner's offsetTop.
  if (innerEl.value) {
    innerObserver = new ResizeObserver(syncInnerOffset);
    // Observe siblings above the inner — that's what shifts `innerOffsetTop`.
    let prev = innerEl.value.previousElementSibling;
    while (prev) {
      innerObserver.observe(prev);
      prev = prev.previousElementSibling;
    }
  }
});

onUnmounted(() => {
  containerObserver?.disconnect();
  containerObserver = null;
  innerObserver?.disconnect();
  innerObserver = null;
});

// Re-emit viewportRange whenever it changes. Computed memoises on
// shallow equality of its return value — but {first,last} is a fresh
// object each time, so we need a manual diff.
let lastEmittedFirst = -2;
let lastEmittedLast = -2;
watch(
  viewportRange,
  (next) => {
    if (next.first === lastEmittedFirst && next.last === lastEmittedLast) {
      return;
    }
    lastEmittedFirst = next.first;
    lastEmittedLast = next.last;
    emit("update:viewportRange", { first: next.first, last: next.last });
  },
  { immediate: true },
);

interface ScrollToIndexOptions {
  smooth?: boolean;
  /** Pixels of viewport to leave above the target item — typically the
   * height of the `#sticky` band, so the row lands just below the
   * pinned toolbar instead of behind it. Default 0. */
  stickyOffset?: number;
}

function scrollToIndex(index: number, options: ScrollToIndexOptions = {}) {
  const root = containerEl.value;
  if (!root) return;
  const offs = offsets.value;
  if (index < 0 || index >= offs.length - 1) return;
  const itemTop = offs[index];
  if (!Number.isFinite(itemTop)) return;
  const stickyOffset = options.stickyOffset ?? 0;
  // The item's flow top in the scroller is `innerOffsetTop + itemTop`.
  // Subtract the sticky band so the row lands below it.
  const target = Math.max(0, innerOffsetTop.value + itemTop - stickyOffset);
  if (options.smooth) {
    root.scrollTo({ top: target, behavior: "smooth" });
  } else {
    root.scrollTop = target;
  }
}

defineExpose({ scrollToIndex, containerEl, scrollTop });

const wrapperStyle = computed(() => {
  const h = props.height;
  if (h === undefined) return { height: "100%" } as const;
  if (typeof h === "number") return { height: `${h}px` } as const;
  return { height: h } as const;
});

const innerStyle = computed(() => ({
  height: `${totalHeight.value}px`,
  position: "relative" as const,
  width: "100%",
}));
</script>

<template>
  <div
    ref="containerEl"
    v-bind="$attrs"
    class="r-virtual-scroller"
    :style="wrapperStyle"
    @scroll.passive="onScroll"
  >
    <div v-if="$slots.prepend" class="r-virtual-scroller__prepend">
      <slot name="prepend" />
    </div>
    <div v-if="$slots.sticky" class="r-virtual-scroller__sticky">
      <slot name="sticky" />
    </div>
    <div ref="innerEl" class="r-virtual-scroller__inner" :style="innerStyle">
      <div
        v-for="entry in renderedItems"
        :key="entry.index"
        class="r-virtual-scroller__item"
        :style="{ transform: `translateY(${entry.top}px)` }"
      >
        <slot :item="entry.item" :index="entry.index" />
      </div>
    </div>
  </div>
</template>

<style scoped>
.r-virtual-scroller {
  overflow-y: auto;
  overflow-x: hidden;
  position: relative;
  background-color: transparent;
}

.r-virtual-scroller__prepend {
  /* `display: contents` makes the wrapper invisible to layout so its
     children become layout-children of the scroller. That matters for
     `position: sticky` consumers inside `#prepend` — sticky pins
     relative to the closest scroll-context ANCESTOR (the scroller),
     but its containing block is its parent in the box tree. With a
     normal `<div>` wrapper here, sticky would un-pin once the wrapper
     scrolls past (its containing block leaves the viewport). With
     `display: contents`, the scroller itself becomes the containing
     block and sticky stays pinned for as long as the scroller has
     scroll travel. */
  display: contents;
}

.r-virtual-scroller__sticky {
  /* Native sticky — pinned by the compositor as the user scrolls past
     the prepend band. Zero JS lag. Consumers should give the slot's
     content an opaque background so virtualised rows scrolling under
     it stay visually hidden. */
  position: sticky;
  top: 0;
  z-index: 5;
}

.r-virtual-scroller__item {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  /* `transform` triggers a compositor layer; the scroll-position-driven
     re-positioning then bypasses paint costs. */
  will-change: transform;
}
</style>
