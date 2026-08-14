<script setup lang="ts" generic="T extends string | number">
// RSliderBtnGroup — segmented/tab control with a sliding pill indicator.
// One active id at a time; the indicator transitions from the previous button
// to the new one on modelValue change.
//
// Variants:
//   * "segmented" — 28×28 icon-only buttons (used by GalleryToolbar).
//   * "tab"       — text-padded tabs (used by AppNav).
//
// Items with `to` render as <router-link> (navigation); items without render
// as <RBtn> and emit update:modelValue on click. Active id is always driven
// externally — the consumer decides it from route, prop, or store.
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import RTooltip from "@/v2/lib/structural/RTooltip/RTooltip.vue";
import RBtn from "../RBtn/RBtn.vue";
import RIcon from "../RIcon/RIcon.vue";
import type { SliderBtnGroupItem } from "./types";

defineOptions({ inheritAttrs: false });

const props = withDefaults(
  defineProps<{
    modelValue: T | null;
    items: SliderBtnGroupItem<T>[];
    variant?: "segmented" | "tab";
    /** Stack direction. `vertical` swaps the indicator from translateX/width
     *  to translateY/height and changes the flex axis. Same aesthetic, same
     *  active-pill slide — just rotated 90°. */
    orientation?: "horizontal" | "vertical";
    ariaLabel?: string;
    /** Disable the whole cluster — dims the container and blocks clicks on
     *  every item, regardless of per-item `disabled`. */
    disabled?: boolean;
    /** Button size. `small` (default) keeps the existing 28×28
     *  segmented vocabulary so every existing call site stays
     *  identical. `x-small` shrinks to 22×22 so the cluster reads as
     *  a peer to RSwitch default (20px) when placed inline inside a
     *  toggle row — mirrors RBtn's x-small / small ladder. */
    size?: "x-small" | "small";
  }>(),
  {
    variant: "segmented",
    orientation: "horizontal",
    ariaLabel: undefined,
    disabled: false,
    size: "small",
  },
);

const emit = defineEmits<{
  (e: "update:modelValue", value: T): void;
}>();

const groupEl = ref<HTMLElement | null>(null);
const btnEls = new Map<T, HTMLElement | null>();
// Indicator geometry — axis-agnostic. `offset` is translateX on
// horizontal and translateY on vertical; `size` is width or height
// respectively. The orientation prop decides how these map to CSS.
const rect = ref({ offset: 0, size: 0, visible: false });
const animate = ref(false);

function setBtnEl(id: T, inst: unknown) {
  if (!inst) {
    btnEls.set(id, null);
    return;
  }
  const el =
    inst instanceof HTMLElement
      ? inst
      : ((inst as { $el?: HTMLElement }).$el ?? null);
  btnEls.set(id, el);
}

function update() {
  const g = groupEl.value;
  if (!g) {
    rect.value = { ...rect.value, visible: false };
    return;
  }
  const active = props.modelValue;
  if (active == null) {
    rect.value = { ...rect.value, visible: false };
    return;
  }
  const el = btnEls.get(active as T);
  if (!el) {
    rect.value = { ...rect.value, visible: false };
    return;
  }
  // Use offsetTop/offsetLeft (layout pixels) instead of
  // getBoundingClientRect (post-transform pixels). When this group
  // is rendered inside a parent that runs an enter transform like
  // `scale(0.92)` (e.g. AppNav's sub-pill drop-in animation), the
  // bounding rect is scaled and the resulting translateY/X embeds
  // the scale factor permanently — the indicator stays misaligned
  // once the transition completes. offsetTop is the un-transformed
  // distance from the offsetParent's padding edge, which is also
  // the indicator's containing-block reference (the slider group
  // has `position: relative`, so the slider group is the offsetParent
  // of the buttons). Both sides now use the same coordinate space.
  if (props.orientation === "vertical") {
    rect.value = {
      offset: el.offsetTop,
      size: el.offsetHeight,
      visible: true,
    };
  } else {
    rect.value = {
      offset: el.offsetLeft,
      size: el.offsetWidth,
      visible: true,
    };
  }
}

watch(
  () => props.modelValue,
  () => nextTick(update),
);
// `items` can change (e.g. responsive label swap); reposition if so.
watch(
  () => props.items,
  () => nextTick(update),
  { deep: true },
);

// `ResizeObserver` covers two cases the old `window.resize` listener
// missed: (a) the group's size changing because of layout shifts that
// don't involve the window (siblings appearing, container resizing);
// and (b) — the actual reason this exists — going from `display: none`
// (bbox = 0×0) to visible. When a parent toggles `v-show`, mounted
// children's `getBoundingClientRect()` returned zero on first
// measure, so the indicator stayed pinned at 0px / width:0. The
// observer re-measures the moment the group gets a real box; on the
// 0→nonzero transition we snap the indicator without animation so it
// doesn't visibly slide in from the left.
let resizeObserver: ResizeObserver | null = null;
let lastGroupWidth = 0;

onMounted(async () => {
  await nextTick();
  update();
  requestAnimationFrame(() => {
    animate.value = true;
  });
  const g = groupEl.value;
  if (g) {
    lastGroupWidth = g.getBoundingClientRect().width;
    resizeObserver = new ResizeObserver(() => {
      const w = g.getBoundingClientRect().width;
      if (lastGroupWidth === 0 && w > 0) {
        animate.value = false;
        update();
        requestAnimationFrame(() => {
          animate.value = true;
        });
      } else {
        update();
      }
      lastGroupWidth = w;
    });
    resizeObserver.observe(g);
  }
});

onBeforeUnmount(() => {
  resizeObserver?.disconnect();
  resizeObserver = null;
});

// `badge` accepts `string | number | null`, so a plain truthiness check would
// still render a pill for the literal "0", and `badge !== 0` misses the string
// "0" / empty string. Centralise the visible-badge rule here.
function showBadge(badge: SliderBtnGroupItem<T>["badge"]): boolean {
  return badge != null && badge !== 0 && badge !== "" && badge !== "0";
}
</script>

<template>
  <!-- `v-bind="$attrs"` so consumer classes / data-attrs / aria flow
       onto the cluster root. `inheritAttrs: false` is kept to keep the
       merge explicit (otherwise event listeners would also auto-attach
       to the root, which we don't want). -->
  <div
    ref="groupEl"
    v-bind="$attrs"
    class="r-slider-btn-group"
    :class="[
      `r-slider-btn-group--${variant}`,
      `r-slider-btn-group--${orientation}`,
      `r-slider-btn-group--size-${size}`,
      { 'r-slider-btn-group--disabled': disabled },
    ]"
    :aria-label="ariaLabel"
    :aria-disabled="disabled || undefined"
    :role="ariaLabel ? 'group' : undefined"
  >
    <span
      class="r-slider-btn-group__indicator"
      :class="{ 'r-slider-btn-group__indicator--animate': animate }"
      :style="
        orientation === 'vertical'
          ? {
              transform: `translateY(${rect.offset}px)`,
              height: `${rect.size}px`,
              opacity: rect.visible && !disabled ? 1 : 0,
            }
          : {
              transform: `translateX(${rect.offset}px)`,
              width: `${rect.size}px`,
              opacity: rect.visible && !disabled ? 1 : 0,
            }
      "
      aria-hidden="true"
    />
    <template v-for="item in items" :key="item.id">
      <router-link
        v-if="item.to"
        :ref="(el) => setBtnEl(item.id, el)"
        :to="item.to"
        class="r-slider-btn-group__btn"
        :class="{ 'r-slider-btn-group__btn--active': item.id === modelValue }"
        :aria-label="item.ariaLabel"
      >
        <RTooltip
          v-if="item.title"
          activator="parent"
          :text="item.title"
          location="top"
        />
        <slot name="item" :item="item" :active="item.id === modelValue">
          <RIcon v-if="item.icon" :icon="item.icon" size="16" />
          <span v-if="item.label" class="r-slider-btn-group__label">
            {{ item.label }}
          </span>
          <span v-if="showBadge(item.badge)" class="r-slider-btn-group__badge">
            {{ item.badge }}
          </span>
        </slot>
      </router-link>
      <RBtn
        v-else
        :ref="(el) => setBtnEl(item.id, el)"
        variant="text"
        density="compact"
        size="x-small"
        class="r-slider-btn-group__btn"
        :class="{ 'r-slider-btn-group__btn--active': item.id === modelValue }"
        :aria-label="item.ariaLabel"
        :aria-pressed="item.id === modelValue"
        :disabled="disabled || item.disabled"
        @click="emit('update:modelValue', item.id)"
      >
        <RTooltip
          v-if="item.title"
          activator="parent"
          :text="item.title"
          location="top"
        />
        <slot name="item" :item="item" :active="item.id === modelValue">
          <RIcon v-if="item.icon" :icon="item.icon" size="16" />
          <span v-if="item.label" class="r-slider-btn-group__label">
            {{ item.label }}
          </span>
          <span v-if="showBadge(item.badge)" class="r-slider-btn-group__badge">
            {{ item.badge }}
          </span>
        </slot>
      </RBtn>
    </template>
  </div>
</template>

<style scoped>
.r-slider-btn-group {
  position: relative;
  display: inline-flex;
  align-items: center;
  border-radius: var(--r-radius-pill);
}

/* Vertical variant — stack items on the Y axis, give the container
   the same shape as a small menu. The sliding indicator continues to
   work (just on the Y axis) thanks to the orientation-aware measure
   in update(). Items stretch to the container's width so they align
   in a clean column. */
.r-slider-btn-group--vertical {
  flex-direction: column;
  align-items: stretch;
  border-radius: var(--r-radius-lg);
}

/* Segmented — thin icon cluster (toolbar-style). 3px padding around the
   28×28 inner buttons + 1px border puts the outer pill at 36px, which
   matches an `RBtn size="default"` sitting next to it (e.g., the disc
   filter / kebab buttons in `GalleryToolbar`). */
.r-slider-btn-group--segmented {
  padding: 3px;
  gap: 2px;
  background: var(--r-color-bg-elevated);
  border: 1px solid var(--r-color-border);
}

/* Tab — text-padded cluster (top-nav style). */
.r-slider-btn-group--tab {
  padding: 4px;
  gap: 2px;
  background: var(--r-color-surface);
  border: 1px solid var(--r-color-border-strong);
  backdrop-filter: blur(20px);
}

.r-slider-btn-group__indicator {
  position: absolute;
  left: 0;
  /* Always a white pill with dark ink on top (the emphasis-pill vocabulary),
     in both themes. Previously fg/bg inverted per theme, which on light gave
     a black pill with light text; the white pill reads better and matches
     the switch knob / nav active treatment. */
  background: var(--r-color-overlay-emphasis-bg);
  border-radius: var(--r-radius-pill);
  pointer-events: none;
  will-change: transform, width;
  opacity: 0;
}

.r-slider-btn-group--segmented.r-slider-btn-group--horizontal
  .r-slider-btn-group__indicator {
  top: 3px;
  bottom: 3px;
}
.r-slider-btn-group--tab.r-slider-btn-group--horizontal
  .r-slider-btn-group__indicator {
  top: 4px;
  bottom: 4px;
}

/* Vertical indicator — span the container's width minus its padding,
   then animate top + height. Mirrors the horizontal case (left/right
   span + animate left + width). `top: 0` is load-bearing: without it,
   the indicator's static position in a column-flex layout sits after
   the flex items, and `translateY(<offset>)` then adds to that,
   shifting the active background downward off the active item. */
.r-slider-btn-group--tab.r-slider-btn-group--vertical
  .r-slider-btn-group__indicator {
  top: 0;
  left: 4px;
  right: 4px;
}
.r-slider-btn-group--segmented.r-slider-btn-group--vertical
  .r-slider-btn-group__indicator {
  top: 0;
  left: 3px;
  right: 3px;
}

.r-slider-btn-group__indicator--animate {
  transition:
    transform var(--r-motion-med) var(--r-motion-ease-out),
    width var(--r-motion-med) var(--r-motion-ease-out),
    height var(--r-motion-med) var(--r-motion-ease-out),
    opacity var(--r-motion-fast) var(--r-motion-ease-out);
}

/* Whole-cluster disabled — dim everything and block clicks. Router-link
   items don't honour a `disabled` prop, so pointer-events:none is the
   reliable escape hatch. The active indicator is hidden via the inline
   opacity binding (see template); the active button must drop its
   inverted text colour too so it reads like every other muted item
   instead of leaving a low-contrast `--r-color-bg` ghost behind. */
.r-slider-btn-group--disabled {
  opacity: 0.4;
  pointer-events: none;
}
.r-slider-btn-group--disabled .r-slider-btn-group__btn--active,
.r-slider-btn-group--disabled .r-slider-btn-group__btn--active:hover {
  color: var(--r-color-fg-secondary) !important;
}

/* Button — common. Indicator owns the active background; buttons stay
   transparent so the slide reads cleanly behind them. `transform` + extra
   transitions give the hover/press animation parity with RBtn's
   currentColor overlay + scale press cue. */
.r-slider-btn-group__btn {
  position: relative;
  z-index: 1;
  border-radius: var(--r-radius-pill) !important;
  text-decoration: none;
  transition:
    color var(--r-motion-fast) var(--r-motion-ease-out),
    background-color var(--r-motion-fast) var(--r-motion-ease-out),
    transform var(--r-motion-fast) var(--r-motion-ease-out);
}
/* Press feedback: subtle scale-down, skipping the active pill so its
   content doesn't pulse during a drag/repeat. */
.r-slider-btn-group__btn:active:not(.r-slider-btn-group__btn--active) {
  transform: scale(0.94);
}

/* Segmented sizing + colors. RBtn's variant styles apply a colour by
   default; to get a neutral grey here we override with equal-or-greater
   specificity + !important. */
.r-slider-btn-group--segmented .r-slider-btn-group__btn {
  min-width: 28px !important;
  min-height: 28px !important;
  width: 28px !important;
  height: 28px !important;
  padding: 0 !important;
  background: transparent !important;
  color: var(--r-color-fg-secondary) !important;
  display: inline-grid;
  place-items: center;
}
.r-slider-btn-group--segmented .r-slider-btn-group__btn :deep(.r-btn__content) {
  min-width: 0;
}
.r-slider-btn-group--segmented
  .r-slider-btn-group__btn:hover:not(.r-slider-btn-group__btn--active) {
  color: var(--r-color-fg) !important;
  background: var(--r-color-surface) !important;
  transform: scale(1.08);
}
.r-slider-btn-group--segmented .r-slider-btn-group__btn--active,
.r-slider-btn-group--segmented .r-slider-btn-group__btn--active:hover {
  color: var(--r-color-overlay-emphasis-fg) !important;
}

/* x-small segmented — 22×22 button cluster, matches RBtn's x-small
   token so the segmented control reads as a peer to a 20px RSwitch
   when sitting inline inside a SettingsToggleRow. Default `small`
   (28×28) keeps every existing call site identical. */
.r-slider-btn-group--segmented.r-slider-btn-group--size-x-small
  .r-slider-btn-group__btn {
  min-width: 22px !important;
  min-height: 22px !important;
  width: 22px !important;
  height: 22px !important;
}
.r-slider-btn-group--segmented.r-slider-btn-group--size-x-small
  .r-slider-btn-group__btn
  :deep(.mdi) {
  font-size: 12px !important;
}

/* Tab sizing + colors. Min-height is set explicitly (and !important)
   so that RBtn-rendered items (no `to`) match the height of router-
   link items. Otherwise Vuetify's RBtn density="compact" + size=
   "x-small" computes a shorter button than the router-link, leading
   to a thin/short hover band on tabs that aren't router-links. */
.r-slider-btn-group--tab .r-slider-btn-group__btn {
  padding: 7px 22px !important;
  min-height: 34px !important;
  font-size: 13.5px;
  font-weight: var(--r-font-weight-medium);
  color: var(--r-color-fg-secondary) !important;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.r-slider-btn-group--tab
  .r-slider-btn-group__btn:hover:not(.r-slider-btn-group__btn--active) {
  color: var(--r-color-fg) !important;
  background: var(--r-color-surface-hover);
}
.r-slider-btn-group--tab .r-slider-btn-group__btn--active,
.r-slider-btn-group--tab .r-slider-btn-group__btn--active:hover {
  color: var(--r-color-overlay-emphasis-fg) !important;
  background: transparent !important;
  font-weight: var(--r-font-weight-semibold);
}

/* Count pill after the label. Background is a translucent tint of the
   current text colour, so it stays legible both on inactive items
   (muted fg) and on the active item (inverted onto the indicator). */
.r-slider-btn-group__badge {
  display: inline-grid;
  place-items: center;
  min-width: 18px;
  height: 18px;
  padding: 0 6px;
  border-radius: var(--r-radius-pill);
  background: color-mix(in srgb, currentColor 18%, transparent);
  font-size: 11px;
  font-weight: var(--r-font-weight-bold);
  line-height: 1;
  font-variant-numeric: tabular-nums;
}
</style>
