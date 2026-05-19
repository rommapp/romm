<script setup lang="ts">
// RProgressLinear — horizontal progress bar primitive. Pairs with
// RProgressCircular: same tone vocabulary, same `indeterminate` /
// `modelValue` split, same colour/size knobs scaled to a horizontal
// surface.
//
//   • Determinate — `modelValue` is a 0–100 percent. The fill grows
//     left-to-right with a smooth width transition so consumers can
//     stream updates without a frame-jump.
//   • Indeterminate — a single slim block slides across the track in
//     a loop. Simpler than Material's two-bar pattern; reads as a clear
//     "working on it" without dragging the eye.
//
// `bufferValue` paints a softer secondary fill behind the primary —
// useful for upload/download streams where bytes ahead of the visible
// progress have already been flushed. `striped` adds a slow diagonal
// sheen for "active" emphasis (busy uploads, ongoing scans).
//
// No label slot — at the typical 4–8px height there's no room to render
// text inside the bar. Consumers compose the percentage / status text
// as a sibling element.
import { computed } from "vue";

defineOptions({ inheritAttrs: false });

interface Props {
  /** Progress value (0–100). Ignored when `indeterminate`. */
  modelValue?: number;
  /** Run the sliding-block animation instead of a static fill. */
  indeterminate?: boolean;
  /** Secondary buffer fill (0–100). Painted behind the primary fill at
   *  reduced opacity. */
  bufferValue?: number;
  /** Track height. Number → px, string → CSS length. Default 4. */
  height?: number | string;
  /** Fill colour. Resolves the lib's TONE_MAP keys or any CSS colour. */
  color?: string;
  /** Track background colour override. Defaults to `--r-color-border`. */
  bgColor?: string;
  /** Pill ends. Default true. */
  rounded?: boolean;
  /** Diagonal stripe overlay — keeps the bar feeling active even when
   *  `modelValue` isn't changing. Ignored when `indeterminate`. */
  striped?: boolean;
  /** Accessible label. Defaults to "Progress". */
  ariaLabel?: string;
}

const props = withDefaults(defineProps<Props>(), {
  modelValue: 0,
  indeterminate: false,
  bufferValue: undefined,
  height: 4,
  color: "primary",
  bgColor: undefined,
  rounded: true,
  striped: false,
  ariaLabel: undefined,
});

// Shared with the rest of the lib — single source of truth so `color`
// is interchangeable between RBtn, RTag, RProgressCircular, etc.
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

const resolvedColor = computed<string>(
  () => TONE_MAP[props.color] ?? props.color ?? TONE_MAP.primary,
);
const resolvedHeight = computed(() =>
  typeof props.height === "number" ? `${props.height}px` : props.height,
);

function clamp(v: number | undefined): number {
  if (v == null || Number.isNaN(v)) return 0;
  return Math.max(0, Math.min(100, v));
}
const clampedValue = computed(() => clamp(props.modelValue));
const clampedBuffer = computed(() =>
  props.bufferValue === undefined ? null : clamp(props.bufferValue),
);

const fillStyle = computed(() =>
  props.indeterminate ? {} : { width: `${clampedValue.value}%` },
);

const ariaValueNow = computed(() =>
  props.indeterminate ? undefined : clampedValue.value,
);

const wrapperStyle = computed(() => {
  const out: Record<string, string> = {
    "--r-prog-h": resolvedHeight.value,
    "--r-prog-color": resolvedColor.value,
  };
  if (props.bgColor) out["--r-prog-bg"] = props.bgColor;
  return out;
});
</script>

<template>
  <div
    class="r-progress-linear"
    :class="{
      'r-progress-linear--indeterminate': indeterminate,
      'r-progress-linear--rounded': rounded,
      'r-progress-linear--striped': striped && !indeterminate,
    }"
    :style="wrapperStyle"
    role="progressbar"
    :aria-label="ariaLabel ?? 'Progress'"
    :aria-valuemin="indeterminate ? undefined : 0"
    :aria-valuemax="indeterminate ? undefined : 100"
    :aria-valuenow="ariaValueNow"
    :aria-busy="indeterminate || undefined"
  >
    <div
      v-if="clampedBuffer !== null && !indeterminate"
      class="r-progress-linear__buffer"
      :style="{ width: `${clampedBuffer}%` }"
    />
    <div class="r-progress-linear__fill" :style="fillStyle" />
  </div>
</template>

<style scoped>
.r-progress-linear {
  position: relative;
  width: 100%;
  height: var(--r-prog-h, 4px);
  background: var(--r-prog-bg, var(--r-color-border));
  overflow: hidden;
}
.r-progress-linear--rounded {
  border-radius: 999px;
}

/* Buffer — sits behind the primary fill, painted in a translucent
   shade of the fill colour so the eye reads "ahead of the bar". */
.r-progress-linear__buffer {
  position: absolute;
  inset-block: 0;
  inset-inline-start: 0;
  background: color-mix(in srgb, var(--r-prog-color) 30%, transparent);
  transition: width var(--r-motion-med) var(--r-motion-ease-out);
}

.r-progress-linear__fill {
  position: absolute;
  inset-block: 0;
  inset-inline-start: 0;
  background: var(--r-prog-color);
  /* Smooth width transitions so streamed updates don't snap-jump. */
  transition: width var(--r-motion-med) var(--r-motion-ease-out);
}

/* Striped — slow diagonal sheen drifting along the fill. Uses
   `white X%` so the same overlay works against any tone. */
.r-progress-linear--striped .r-progress-linear__fill {
  background-image: linear-gradient(
    45deg,
    color-mix(in srgb, white 18%, transparent) 25%,
    transparent 25%,
    transparent 50%,
    color-mix(in srgb, white 18%, transparent) 50%,
    color-mix(in srgb, white 18%, transparent) 75%,
    transparent 75%,
    transparent
  );
  background-size: 1rem 1rem;
  animation: r-progress-stripe 1s linear infinite;
}
@keyframes r-progress-stripe {
  from {
    background-position: 0 0;
  }
  to {
    background-position: 1rem 0;
  }
}

/* Indeterminate — single block slides across the track on a loop.
   `inset-inline-*` so RTL flips the direction automatically without
   a separate keyframe set. */
.r-progress-linear--indeterminate .r-progress-linear__fill {
  width: auto;
  inset-inline-start: -35%;
  inset-inline-end: 100%;
  animation: r-progress-indeterminate 1.8s cubic-bezier(0.65, 0.05, 0.35, 1)
    infinite;
}
@keyframes r-progress-indeterminate {
  0% {
    inset-inline-start: -35%;
    inset-inline-end: 100%;
  }
  60% {
    inset-inline-start: 100%;
    inset-inline-end: -35%;
  }
  100% {
    inset-inline-start: 100%;
    inset-inline-end: -35%;
  }
}

@media (prefers-reduced-motion: reduce) {
  .r-progress-linear__fill,
  .r-progress-linear__buffer {
    transition: none;
  }
  .r-progress-linear--striped .r-progress-linear__fill,
  .r-progress-linear--indeterminate .r-progress-linear__fill {
    animation: none;
  }
  .r-progress-linear--indeterminate .r-progress-linear__fill {
    inset-inline-start: 0;
    inset-inline-end: 0;
  }
}
</style>
