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
import {
  computed,
  nextTick,
  onBeforeUnmount,
  onMounted,
  ref,
  watch,
} from "vue";
import RIcon from "../../primitives/RIcon/RIcon.vue";
import RImg from "../../primitives/RImg/RImg.vue";
import type { RTabNavItem } from "./types";

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
const navEl = ref<HTMLElement | null>(null);
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
  const nav = navEl.value;
  if (!nav) {
    indicator.value = { ...indicator.value, visible: false };
    return;
  }
  const el = btnEls.get(props.modelValue);
  if (!el) {
    indicator.value = { ...indicator.value, visible: false };
    return;
  }
  const navRect = nav.getBoundingClientRect();
  const btnRect = el.getBoundingClientRect();
  // Account for horizontal scroll inside an overflow-x:auto nav.
  const scrollLeft = nav.scrollLeft;
  indicator.value = {
    left: btnRect.left - navRect.left + scrollLeft,
    width: btnRect.width,
    visible: true,
  };
}

watch(
  () => props.modelValue,
  () => nextTick(update),
);
watch(visibleItems, () => nextTick(update), { deep: true });
watch(
  () => props.variant,
  () => nextTick(update),
);

let resizeObserver: ResizeObserver | null = null;
let lastNavWidth = 0;

onMounted(async () => {
  await nextTick();
  update();
  // Snap into place on the first frame, then enable the transition so
  // subsequent picks slide. Without this the indicator visibly jumps
  // from (0, 0) to its final position on mount.
  requestAnimationFrame(() => {
    animate.value = true;
  });
  const nav = navEl.value;
  if (nav) {
    lastNavWidth = nav.getBoundingClientRect().width;
    resizeObserver = new ResizeObserver(() => {
      const w = nav.getBoundingClientRect().width;
      // 0→nonzero (display:none → visible): re-measure without
      // animation so the indicator doesn't slide in from the left.
      if (lastNavWidth === 0 && w > 0) {
        animate.value = false;
        update();
        requestAnimationFrame(() => {
          animate.value = true;
        });
      } else {
        update();
      }
      lastNavWidth = w;
    });
    resizeObserver.observe(nav);
  }
});

onBeforeUnmount(() => {
  resizeObserver?.disconnect();
  resizeObserver = null;
});
</script>

<template>
  <nav
    ref="navEl"
    v-bind="$attrs"
    class="r-tab-nav"
    :class="[
      `r-tab-nav--${size}`,
      `r-tab-nav--${variant}`,
      `r-tab-nav--${orientation}`,
    ]"
    role="tablist"
    :aria-orientation="orientation"
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
        :alt="t.label"
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
  </nav>
</template>

<style scoped>
.r-tab-nav {
  display: flex;
  gap: 0;
  position: relative;
}
.r-tab-nav--horizontal {
  flex-direction: row;
  overflow-x: auto;
  scrollbar-width: none;
}
.r-tab-nav--horizontal::-webkit-scrollbar {
  display: none;
}
.r-tab-nav--vertical {
  flex-direction: column;
}

.r-tab-nav__btn {
  appearance: none;
  background: transparent;
  border: none;
  cursor: pointer;
  white-space: nowrap;
  /* Keep natural width so the horizontal nav scrolls on overflow
     (`.r-tab-nav--horizontal { overflow-x: auto }`) instead of squishing
     the tabs below their content on narrow viewports. */
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
.r-tab-nav--pill {
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
