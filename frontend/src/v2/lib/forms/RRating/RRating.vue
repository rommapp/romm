<script setup lang="ts">
// RRating — Vuetify-free. A row of N icon-buttons that paint as
// "full" up to the model value and "empty" past it. Click sets the
// value to that index+1; clicking the current value clears it when
// `clearable` is on.
//
// Half-increment support: when `halfIncrements` is on, each star is
// split into left/right halves — hovering / clicking the left half
// reports `i + 0.5`, the right half reports `i + 1`.
//
// Motion vocabulary matches the rest of the lib: hover lift + scale
// via cubic-bezier(0.34, 1.56, 0.64, 1), active press squash, filled
// stars get a "pop" entrance when they first cross the threshold.
import { computed, ref } from "vue";
import RIcon from "../../primitives/RIcon/RIcon.vue";

defineOptions({ inheritAttrs: false });

interface Props {
  modelValue?: number;
  length?: number | string;
  /** Tone for filled icons. Keyword or kebab-case token. */
  color?: string;
  /** Tone for the *active* portion. Defaults to `color`. */
  activeColor?: string;
  emptyIcon?: string;
  fullIcon?: string;
  halfIcon?: string;
  clearable?: boolean;
  size?:
    | "x-small"
    | "small"
    | "default"
    | "large"
    | "x-large"
    | string
    | number;
  readonly?: boolean;
  halfIncrements?: boolean;
  density?: "default" | "comfortable" | "compact";
  /** Whether to react to hover (preview on hover). */
  hover?: boolean;
  /** Accessible labels per item (e.g. ["bad","ok","good","great","perfect"]). */
  itemLabels?: string[];
  /** Optional shared aria-label for the whole row. */
  ariaLabel?: string;
}

const props = withDefaults(defineProps<Props>(), {
  modelValue: 0,
  length: 5,
  color: "romm-gold",
  activeColor: undefined,
  emptyIcon: "mdi-star-outline",
  fullIcon: "mdi-star",
  halfIcon: "mdi-star-half-full",
  clearable: false,
  size: "default",
  readonly: false,
  halfIncrements: false,
  density: "default",
  hover: false,
  itemLabels: undefined,
  ariaLabel: undefined,
});

const emit = defineEmits<{
  (e: "update:modelValue", value: number): void;
}>();

// ── Tone resolver — same vocabulary as the rest of the lib. ─────
const TONE_MAP: Record<string, string> = {
  primary: "var(--r-color-brand-primary)",
  secondary: "var(--r-color-brand-secondary)",
  accent: "var(--r-color-brand-accent)",
  success: "var(--r-color-success)",
  warning: "var(--r-color-warning)",
  danger: "var(--r-color-danger)",
  error: "var(--r-color-danger)",
  info: "var(--r-color-info)",
  "romm-red": "var(--r-color-romm-red)",
  "romm-green": "var(--r-color-romm-green)",
  "romm-blue": "var(--r-color-romm-blue)",
  "romm-gold": "var(--r-color-romm-gold)",
};
function resolveColor(value: string): string {
  if (TONE_MAP[value]) return TONE_MAP[value];
  if (/^[a-z][a-z0-9-]*$/i.test(value)) {
    return `var(--r-color-${value}, ${value})`;
  }
  return value;
}
const fillColor = computed(() =>
  resolveColor(props.activeColor ?? props.color),
);
const emptyColor = computed(() => resolveColor(props.color));

const itemCount = computed(() => Number(props.length) || 5);

// Hover preview state — when the user hovers, the row paints up to
// the hovered value instead of the model value (only when `hover` is on).
const hoverValue = ref<number | null>(null);

// The value used to drive the paint. Hover preview wins when active.
const paintValue = computed(() =>
  hoverValue.value != null ? hoverValue.value : props.modelValue,
);

interface ItemState {
  index: number;
  full: boolean;
  half: boolean;
  empty: boolean;
}
const items = computed<ItemState[]>(() => {
  const v = paintValue.value;
  const arr: ItemState[] = [];
  for (let i = 0; i < itemCount.value; i++) {
    const full = v >= i + 1;
    const half = !full && v >= i + 0.5;
    arr.push({ index: i, full, half, empty: !full && !half });
  }
  return arr;
});

function valueForClick(i: number, half: boolean): number {
  // Half-increments: left half = i + 0.5, right half = i + 1.
  const base = props.halfIncrements && half ? i + 0.5 : i + 1;
  // `clearable`: clicking on the current value clears it (→ 0).
  if (props.clearable && props.modelValue === base) return 0;
  return base;
}

function onClick(i: number, half: boolean) {
  if (props.readonly) return;
  emit("update:modelValue", valueForClick(i, half));
}

function onMouseEnter(i: number, half: boolean) {
  if (props.readonly || !props.hover) return;
  hoverValue.value = props.halfIncrements && half ? i + 0.5 : i + 1;
}
function onMouseLeave() {
  hoverValue.value = null;
}

// ── Size ────────────────────────────────────────────────────────
// Vuetify size names → px sizes; numeric input passes through.
const SIZE_MAP: Record<string, string> = {
  "x-small": "14px",
  small: "18px",
  default: "22px",
  large: "28px",
  "x-large": "36px",
};
const iconSize = computed(() => {
  const s = String(props.size);
  if (SIZE_MAP[s]) return SIZE_MAP[s];
  if (/^\d+$/.test(s)) return `${s}px`;
  return s;
});

// Density → gap between items.
const GAP_MAP = {
  default: "4px",
  comfortable: "2px",
  compact: "0px",
};
const gap = computed(() => GAP_MAP[props.density]);
</script>

<template>
  <div
    v-bind="$attrs"
    class="r-rating"
    :class="{
      'r-rating--readonly': readonly,
      'r-rating--hover': hover && !readonly,
    }"
    :style="{
      '--r-rating-fill': fillColor,
      '--r-rating-empty': emptyColor,
      '--r-rating-size': iconSize,
      '--r-rating-gap': gap,
    }"
    role="radiogroup"
    :aria-label="ariaLabel"
    :aria-readonly="readonly || undefined"
    @mouseleave="onMouseLeave"
  >
    <button
      v-for="item in items"
      :key="item.index"
      type="button"
      class="r-rating__item"
      :class="{
        'r-rating__item--full': item.full,
        'r-rating__item--half': item.half,
        'r-rating__item--empty': item.empty,
      }"
      :disabled="readonly"
      :aria-label="
        itemLabels?.[item.index] ?? `${item.index + 1} of ${itemCount}`
      "
      :aria-checked="modelValue === item.index + 1"
      role="radio"
      @click="onClick(item.index, false)"
      @mouseenter="onMouseEnter(item.index, false)"
    >
      <!-- Half-increment hot zones — invisible left/right hover targets
           that report the half / full value. Only when halfIncrements
           is on. -->
      <span
        v-if="halfIncrements"
        class="r-rating__half r-rating__half--left"
        @click.stop="onClick(item.index, true)"
        @mouseenter="onMouseEnter(item.index, true)"
      />
      <span
        v-if="halfIncrements"
        class="r-rating__half r-rating__half--right"
        @click.stop="onClick(item.index, false)"
        @mouseenter="onMouseEnter(item.index, false)"
      />

      <!-- Visible icon. `key` flip on the icon name forces a remount
           so the pop animation runs each time it changes. -->
      <RIcon
        :key="item.full ? 'full' : item.half ? 'half' : 'empty'"
        :icon="item.full ? fullIcon : item.half ? halfIcon : emptyIcon"
        :size="iconSize"
        class="r-rating__icon"
        :class="{
          'r-rating__icon--full': item.full,
          'r-rating__icon--half': item.half,
        }"
      />
    </button>
  </div>
</template>

<style scoped>
.r-rating {
  display: inline-flex;
  align-items: center;
  gap: var(--r-rating-gap, 4px);
  --r-rating-fill: var(--r-color-romm-gold);
  --r-rating-empty: var(--r-color-romm-gold);
  --r-rating-size: 22px;
  --r-rating-gap: 4px;
}

.r-rating__item {
  appearance: none;
  background: transparent;
  border: 0;
  padding: 4px;
  margin: 0;
  cursor: pointer;
  font: inherit;
  color: inherit;
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 6px;
  transition:
    transform var(--r-motion-fast) cubic-bezier(0.34, 1.56, 0.64, 1),
    filter var(--r-motion-fast) var(--r-motion-ease-out);
  will-change: transform;
}
.r-rating__item:disabled {
  cursor: default;
}

.r-rating:not(.r-rating--readonly) .r-rating__item:hover {
  transform: translateY(-2px) scale(1.12);
  filter: drop-shadow(0 4px 8px color-mix(in srgb, black 35%, transparent));
}
.r-rating:not(.r-rating--readonly) .r-rating__item:active {
  transform: scale(0.92);
  transition: transform 90ms var(--r-motion-ease-out);
}

/* ── Icon paint ──────────────────────────────────────────────── */
.r-rating__icon {
  color: color-mix(in srgb, var(--r-rating-empty) 35%, transparent);
  transition: color var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-rating__icon--full,
.r-rating__icon--half {
  color: var(--r-rating-fill);
  /* Pop animation when an icon enters its filled state. `:key`-based
     remount on the icon ensures the animation fires on each crossing
     instead of staying put. */
  animation: r-rating-pop var(--r-motion-med) var(--r-motion-ease-out);
}
@keyframes r-rating-pop {
  0% {
    transform: scale(0.6);
  }
  60% {
    transform: scale(1.18);
  }
  100% {
    transform: scale(1);
  }
}

/* ── Half-increment hot zones ────────────────────────────────── */
.r-rating__half {
  position: absolute;
  top: 0;
  bottom: 0;
  width: 50%;
  z-index: 1;
}
.r-rating__half--left {
  left: 0;
}
.r-rating__half--right {
  right: 0;
}

/* Modality-gated focus ring — only on key/pad input. */
html[data-input="key"] .r-rating__item:focus-visible,
html[data-input="pad"] .r-rating__item:focus-visible {
  outline: 2px solid var(--r-rating-fill);
  outline-offset: 2px;
}

/* Readonly — drop the lift; the row reads as static info. */
.r-rating--readonly .r-rating__item {
  cursor: default;
  pointer-events: none;
}

@media (prefers-reduced-motion: reduce) {
  .r-rating__item,
  .r-rating__icon {
    transition: none !important;
    animation: none !important;
  }
}
</style>
