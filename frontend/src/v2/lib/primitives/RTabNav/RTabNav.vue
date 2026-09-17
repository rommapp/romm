<script setup lang="ts">
// RTabNav — single component, two visual presentations:
//   * variant="underlined" (default) — horizontal nav with a brand
//     underline on active. Used for primary tabs and tight subtabs.
//     The underline is a sliding indicator (parallels RSliderBtnGroup)
//     that translates between buttons on `modelValue` change.
//   * variant="pill" — stacked menu-like items with a soft rounded
//     fill on active. Pairs naturally with `orientation="vertical"`
//     for left-rail subtabs (SaveDataTab style).
//
// Items can carry an optional leading icon and an optional badge
// (string | number). Items with `show: false` are filtered out so
// callers can pass a single declarative source.
//
// A horizontal strip that overflows fades its clipped edges and shows a
// chevron there, so a narrow viewport still reads as "more tabs this way".
import {
  computed,
  nextTick,
  onBeforeUnmount,
  onMounted,
  ref,
  watch,
} from "vue";
import { useReducedMotion } from "@/v2/composables/useReducedMotion";
import RIcon from "../../primitives/RIcon/RIcon.vue";
import RImg from "../../primitives/RImg/RImg.vue";
import type { RTabNavItem } from "./types";

// Width of the faded edge, also the margin kept when scrolling a tab into view
// so it never lands under the fade.
const EDGE_PX = 40;

defineOptions({ inheritAttrs: false });

interface Props {
  modelValue: string;
  items: RTabNavItem[];
  /** Size ladder shared with RBtn / RChip / RTag. */
  size?: "x-small" | "small" | "default" | "large" | "x-large";
  variant?: "underlined" | "pill";
  orientation?: "horizontal" | "vertical";
}

const props = withDefaults(defineProps<Props>(), {
  size: "default",
  variant: "underlined",
  orientation: "horizontal",
});

defineEmits<{
  (e: "update:modelValue", v: string): void;
}>();

const visibleItems = computed(() =>
  props.items.filter((x) => x.show !== false),
);

// ---------- Sliding underline indicator (underlined variant only) ----------
const trackEl = ref<HTMLElement | null>(null);
const btnEls = new Map<string, HTMLElement | null>();
const indicator = ref({ left: 0, width: 0, visible: false });
const animate = ref(false);

function setBtnEl(id: string, el: Element | null) {
  btnEls.set(id, el as HTMLElement | null);
}

function update() {
  if (props.variant !== "underlined") {
    indicator.value = { ...indicator.value, visible: false };
    return;
  }
  const track = trackEl.value;
  if (!track) {
    indicator.value = { ...indicator.value, visible: false };
    return;
  }
  const el = btnEls.get(props.modelValue);
  if (!el) {
    indicator.value = { ...indicator.value, visible: false };
    return;
  }
  const trackRect = track.getBoundingClientRect();
  const btnRect = el.getBoundingClientRect();
  // Account for horizontal scroll inside an overflow-x:auto track.
  const scrollLeft = track.scrollLeft;
  indicator.value = {
    left: btnRect.left - trackRect.left + scrollLeft,
    width: btnRect.width,
    visible: true,
  };
}

// ---------- Overflow hints (horizontal only) ----------
const { enabled: reducedMotion } = useReducedMotion();
const overflowStart = ref(false);
const overflowEnd = ref(false);

function scrollBehavior(): ScrollBehavior {
  return reducedMotion.value ? "auto" : "smooth";
}

function updateOverflow() {
  const track = trackEl.value;
  if (!track || props.orientation !== "horizontal") {
    overflowStart.value = false;
    overflowEnd.value = false;
    return;
  }
  // 1px slack: fractional tab widths leave a sub-pixel scroll range that
  // would otherwise keep the end hint lit at the very end of the strip.
  const maxScroll = track.scrollWidth - track.clientWidth;
  overflowStart.value = track.scrollLeft > 1;
  overflowEnd.value = track.scrollLeft < maxScroll - 1;
}

function reveal(el: HTMLElement | null | undefined, behavior: ScrollBehavior) {
  const track = trackEl.value;
  if (!track || !el || props.orientation !== "horizontal") return;
  const start = el.offsetLeft - EDGE_PX;
  const end = el.offsetLeft + el.offsetWidth + EDGE_PX - track.clientWidth;
  if (start < track.scrollLeft) {
    track.scrollTo({ left: Math.max(start, 0), behavior });
  } else if (end > track.scrollLeft) {
    track.scrollTo({ left: end, behavior });
  }
}

function revealActive(behavior: ScrollBehavior) {
  reveal(btnEls.get(props.modelValue), behavior);
}

// The browser's own focus scroll stops at the edge, under the fade and chevron.
function onTrackFocusIn(event: FocusEvent) {
  const el = event.target as HTMLElement;
  if (el.matches(":focus-visible")) reveal(el, scrollBehavior());
}

function scrollPage(direction: 1 | -1) {
  const track = trackEl.value;
  if (!track) return;
  track.scrollBy({
    left: direction * (track.clientWidth - EDGE_PX * 2),
    behavior: scrollBehavior(),
  });
}

watch(
  () => props.modelValue,
  () =>
    nextTick(() => {
      update();
      revealActive(scrollBehavior());
    }),
);
watch([visibleItems, () => props.variant, () => props.orientation], () =>
  nextTick(() => {
    update();
    updateOverflow();
  }),
);

let resizeObserver: ResizeObserver | null = null;
let lastTrackWidth = 0;

onMounted(async () => {
  await nextTick();
  update();
  revealActive("auto");
  updateOverflow();
  // Snap into place on the first frame, then enable the transition so
  // subsequent picks slide. Without this the indicator visibly jumps
  // from (0, 0) to its final position on mount.
  requestAnimationFrame(() => {
    animate.value = true;
  });
  const track = trackEl.value;
  if (track) {
    lastTrackWidth = track.getBoundingClientRect().width;
    resizeObserver = new ResizeObserver(() => {
      const w = track.getBoundingClientRect().width;
      // 0→nonzero (display:none → visible): re-measure without
      // animation so the indicator doesn't slide in from the left.
      if (lastTrackWidth === 0 && w > 0) {
        animate.value = false;
        update();
        revealActive("auto");
        requestAnimationFrame(() => {
          animate.value = true;
        });
      } else {
        update();
      }
      updateOverflow();
      lastTrackWidth = w;
    });
    resizeObserver.observe(track);
  }
});

onBeforeUnmount(() => {
  resizeObserver?.disconnect();
  resizeObserver = null;
});
</script>

<template>
  <nav
    v-bind="$attrs"
    class="r-tab-nav"
    :class="[
      `r-tab-nav--${size}`,
      `r-tab-nav--${variant}`,
      `r-tab-nav--${orientation}`,
      {
        'r-tab-nav--overflow-start': overflowStart,
        'r-tab-nav--overflow-end': overflowEnd,
      },
    ]"
    :style="{ '--r-tab-nav-edge': `${EDGE_PX}px` }"
    role="tablist"
    :aria-orientation="orientation"
  >
    <div
      ref="trackEl"
      class="r-tab-nav__track"
      @scroll.passive="updateOverflow"
      @focusin="onTrackFocusIn"
    >
      <button
        v-for="t in visibleItems"
        :key="t.id"
        :ref="(el) => setBtnEl(t.id, el as Element | null)"
        type="button"
        role="tab"
        class="r-tab-nav__btn"
        :class="{ 'r-tab-nav__btn--active': modelValue === t.id }"
        :aria-selected="modelValue === t.id"
        @click="$emit('update:modelValue', t.id)"
      >
        <RImg
          v-if="t.image"
          :src="t.image"
          alt=""
          width="1em"
          height="1em"
          contain
          class="r-tab-nav__image"
        />
        <RIcon v-else-if="t.icon" :icon="t.icon" class="r-tab-nav__icon" />
        <span class="r-tab-nav__label">{{ t.label }}</span>
        <span
          v-if="t.badge !== undefined && t.badge !== null && t.badge !== ''"
          class="r-tab-nav__badge"
        >
          {{ t.badge }}
        </span>
      </button>

      <span
        v-if="variant === 'underlined'"
        class="r-tab-nav__indicator"
        :class="{ 'r-tab-nav__indicator--animate': animate }"
        :style="{
          transform: `translateX(${indicator.left}px)`,
          width: `${indicator.width}px`,
          opacity: indicator.visible ? 1 : 0,
        }"
        aria-hidden="true"
      />
    </div>

    <!-- Pointer-only shortcuts: keyboard and pad reach every tab directly,
         and focusing one scrolls it into view. -->
    <button
      v-if="overflowStart"
      type="button"
      tabindex="-1"
      aria-hidden="true"
      class="r-tab-nav__edge r-tab-nav__edge--start"
      @mousedown.prevent
      @click="scrollPage(-1)"
    >
      <RIcon icon="mdi-chevron-left" size="18" />
    </button>
    <button
      v-if="overflowEnd"
      type="button"
      tabindex="-1"
      aria-hidden="true"
      class="r-tab-nav__edge r-tab-nav__edge--end"
      @mousedown.prevent
      @click="scrollPage(1)"
    >
      <RIcon icon="mdi-chevron-right" size="18" />
    </button>
  </nav>
</template>

<style scoped>
.r-tab-nav {
  position: relative;
  /* The track scrolls, not the nav, so without this a flex or grid parent
     sizes the nav to every tab and the strip overflows instead of scrolling. */
  min-width: 0;
}
.r-tab-nav__track {
  display: flex;
  gap: 0;
  position: relative;
}
.r-tab-nav--horizontal .r-tab-nav__track {
  flex-direction: row;
  /* Scroll horizontally to reach overflowing tabs, but stay OUT of the
     vertical axis: `overflow-y: hidden` (not the `auto` that `overflow-x`
     would otherwise force) means the strip isn't a vertical scroll
     container, so a vertical-dominant touch swipe isn't latched here — it
     chains to the page scroller and the view still scrolls when the swipe
     starts on the tabs. (`touch-action: pan-x` can't do this: per spec it
     removes vertical panning from the whole gesture, freezing the page.)
     `overscroll-behavior-x: contain` stops the horizontal overscroll from
     chaining / rubber-banding. */
  overflow-x: auto;
  overflow-y: hidden;
  overscroll-behavior-x: contain;
  scrollbar-width: none;
}
.r-tab-nav--horizontal .r-tab-nav__track::-webkit-scrollbar {
  display: none;
}
.r-tab-nav--vertical .r-tab-nav__track {
  flex-direction: column;
}

/* ---------- Overflow hints ----------
   Fade whichever edge clips tabs and park a chevron over it. The mask sits on
   the track only, so the nav's baseline and the chevrons stay crisp. */
.r-tab-nav--overflow-start .r-tab-nav__track {
  --r-tab-nav-fade-start: var(--r-tab-nav-edge);
}
.r-tab-nav--overflow-end .r-tab-nav__track {
  --r-tab-nav-fade-end: var(--r-tab-nav-edge);
}
.r-tab-nav--overflow-start .r-tab-nav__track,
.r-tab-nav--overflow-end .r-tab-nav__track {
  mask-image: linear-gradient(
    to right,
    transparent,
    black var(--r-tab-nav-fade-start, 0px),
    black calc(100% - var(--r-tab-nav-fade-end, 0px)),
    transparent
  );
}
.r-tab-nav__edge {
  appearance: none;
  position: absolute;
  top: 0;
  bottom: 0;
  z-index: 2;
  display: grid;
  place-items: center;
  width: calc(var(--r-tab-nav-edge) * 0.6);
  padding: 0;
  border: none;
  background: transparent;
  color: var(--r-color-fg-secondary);
  cursor: pointer;
  transition: color var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-tab-nav__edge:hover {
  color: var(--r-color-fg);
}
.r-tab-nav__edge--start {
  left: 0;
  justify-items: start;
}
.r-tab-nav__edge--end {
  right: 0;
  justify-items: end;
}

.r-tab-nav__btn {
  appearance: none;
  background: transparent;
  border: none;
  cursor: pointer;
  white-space: nowrap;
  /* Anchor + own stacking context for the contained focus highlight
     (below), so its `z-index: -1` pseudo stays behind the label but above
     the button's own background. The underlined variant raises this to 1. */
  position: relative;
  z-index: 0;
  /* Keep natural width so the horizontal track scrolls on overflow
     instead of squishing the tabs below their content on narrow viewports. */
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-family: inherit;
  font-weight: var(--r-font-weight-medium);
  color: var(--r-color-fg-muted);
  transition:
    background var(--r-motion-fast) var(--r-motion-ease-out),
    color var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-tab-nav__btn:not(.r-tab-nav__btn--active):hover {
  color: var(--r-color-fg-secondary);
}
.r-tab-nav__icon {
  flex-shrink: 0;
}
/* Image variant — provider logos / brand marks. RImg owns the inner
   <img>; we round its outer wrapper and ride opacity from "muted at
   rest" to "full saturation on hover/active" so the brand mark stands
   out only when it's the focus of the surface. */
.r-tab-nav__image {
  flex-shrink: 0;
  border-radius: 3px;
  opacity: 0.65;
  transition: opacity var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-tab-nav__btn:hover .r-tab-nav__image,
.r-tab-nav__btn--active .r-tab-nav__image {
  opacity: 1;
}
.r-tab-nav__label {
  flex: 1;
  text-align: left;
}

/* ---------- Focus ----------
   The global modality-gated ring (global.css) is an `outline`, which the
   track's `overflow-y: hidden` clip slices into two vertical slivers on
   either side of the focused tab. Suppress it and paint a contained,
   rounded highlight that lives INSIDE the button (a pseudo-element, so
   nothing can be clipped away). Gated to keyboard / pad exactly like the
   global rule. The `::before` sits behind the label (z-index: -1) and
   leaves the bottom edge clear so the active tab's underline still reads. */
html:not([data-input]) .r-tab-nav__btn:focus-visible,
html[data-input="key"] .r-tab-nav__btn:focus-visible,
html[data-input="pad"] .r-tab-nav__btn:focus-visible {
  outline: none;
}
html:not([data-input]) .r-tab-nav__btn:focus-visible::before,
html[data-input="key"] .r-tab-nav__btn:focus-visible::before,
html[data-input="pad"] .r-tab-nav__btn:focus-visible::before {
  content: "";
  position: absolute;
  inset: 3px 3px 5px;
  z-index: -1;
  border-radius: var(--r-radius-sm);
  background: var(--r-color-surface-hover);
  box-shadow: inset 0 0 0 2px var(--r-color-focus);
  pointer-events: none;
}

/* ---------- Underlined variant (horizontal only) ---------- */
.r-tab-nav--underlined {
  border-bottom: 1px solid var(--r-color-border-strong);
}
.r-tab-nav--underlined .r-tab-nav__btn {
  border-radius: 0;
  position: relative;
  z-index: 1;
}
.r-tab-nav--underlined .r-tab-nav__btn--active {
  color: var(--r-color-fg);
}
.r-tab-nav--underlined.r-tab-nav--x-small .r-tab-nav__btn {
  padding: 4px 8px;
  font-size: 11px;
}
.r-tab-nav--underlined.r-tab-nav--small .r-tab-nav__btn {
  padding: 6px 12px;
  font-size: 12px;
}
.r-tab-nav--underlined.r-tab-nav--default .r-tab-nav__btn {
  padding: 8px 18px;
  font-size: 13px;
}
.r-tab-nav--underlined.r-tab-nav--large .r-tab-nav__btn {
  padding: 10px 24px;
  font-size: var(--r-font-size-lg);
}
.r-tab-nav--underlined.r-tab-nav--x-large .r-tab-nav__btn {
  padding: 12px 28px;
  font-size: var(--r-font-size-xl);
}

/* Sliding underline — sits on the bottom border line, slides between
   buttons on modelValue change (parallels RSliderBtnGroup's indicator). */
.r-tab-nav__indicator {
  position: absolute;
  left: 0;
  bottom: -1px;
  height: 2px;
  background: var(--r-color-brand-primary);
  border-radius: 2px 2px 0 0;
  pointer-events: none;
  will-change: transform, width;
  opacity: 0;
}
.r-tab-nav__indicator--animate {
  transition:
    transform var(--r-motion-med) var(--r-motion-ease-out),
    width var(--r-motion-med) var(--r-motion-ease-out),
    opacity var(--r-motion-fast) var(--r-motion-ease-out);
}

/* ---------- Pill variant ---------- */
.r-tab-nav--pill .r-tab-nav__track {
  gap: 4px;
}
.r-tab-nav--pill .r-tab-nav__btn {
  border-radius: var(--r-radius-md);
  background: transparent;
}
.r-tab-nav--pill .r-tab-nav__btn:not(.r-tab-nav__btn--active):hover {
  background: var(--r-color-surface-hover);
  color: var(--r-color-fg);
}
.r-tab-nav--pill .r-tab-nav__btn--active {
  background: color-mix(in srgb, var(--r-color-brand-primary) 18%, transparent);
  color: var(--r-color-brand-primary);
}
.r-tab-nav--pill .r-tab-nav__btn--active .r-tab-nav__icon {
  color: var(--r-color-brand-primary);
}
.r-tab-nav--pill.r-tab-nav--x-small .r-tab-nav__btn {
  padding: 6px 8px;
  font-size: 11px;
}
.r-tab-nav--pill.r-tab-nav--small .r-tab-nav__btn {
  padding: 8px 12px;
  font-size: 12px;
}
.r-tab-nav--pill.r-tab-nav--default .r-tab-nav__btn {
  padding: 10px 14px;
  font-size: 13px;
}
.r-tab-nav--pill.r-tab-nav--large .r-tab-nav__btn {
  padding: 12px 18px;
  font-size: var(--r-font-size-lg);
}
.r-tab-nav--pill.r-tab-nav--x-large .r-tab-nav__btn {
  padding: 14px 22px;
  font-size: var(--r-font-size-xl);
}

/* ---------- Badge ---------- */
.r-tab-nav__badge {
  display: inline-flex;
  align-items: center;
  padding: 1px 7px;
  border-radius: var(--r-radius-full);
  background: var(--r-color-surface);
  border: 1px solid var(--r-color-border);
  color: var(--r-color-fg-muted);
  font-size: 10.5px;
  font-weight: var(--r-font-weight-semibold);
  font-variant-numeric: tabular-nums;
  line-height: 1.4;
  flex-shrink: 0;
  transition:
    background var(--r-motion-fast) var(--r-motion-ease-out),
    color var(--r-motion-fast) var(--r-motion-ease-out),
    border-color var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-tab-nav__btn--active .r-tab-nav__badge {
  background: color-mix(in srgb, var(--r-color-brand-primary) 18%, transparent);
  border-color: color-mix(
    in srgb,
    var(--r-color-brand-primary) 50%,
    transparent
  );
  color: var(--r-color-brand-primary);
}

html[data-bp~="sm-and-down"]
  .r-tab-nav--underlined.r-tab-nav--default
  .r-tab-nav__btn {
  padding: 8px 14px;
  font-size: 12px;
}
</style>
