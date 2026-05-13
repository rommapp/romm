<script setup lang="ts">
// RProgressCircular — Vuetify-free. Pure SVG ring with two modes:
//
//   • Indeterminate (default) — Material-style spinner. The SVG rotates
//     continuously while the arc's `stroke-dasharray` cycles through a
//     short→long→short pattern, creating the classic "snake chasing
//     its tail" loop. Two animations compose on one DOM element so we
//     don't need a wrapper rotation.
//
//   • Determinate (`indeterminate=false` + `modelValue`) — the arc fills
//     clockwise from 12 o'clock. `pathLength="100"` normalises the
//     circle so `stroke-dashoffset = 100 - value` works at any radius —
//     no per-size maths.
//
// `size` and `width` are numeric pixels (number or numeric string).
// Anything else falls back to the default. Colour goes through the
// shared TONE_MAP so `"primary"`, status tones, and legacy `romm-*`
// names resolve consistently with the rest of the lib.
//
// Default slot — overlay content centred over the ring (percentage
// text, status icon). Lives outside the SVG so it isn't rotated.
import { computed, useSlots } from "vue";

defineOptions({ inheritAttrs: false });

interface Props {
  /** Spinner mode. Default `true` — Material-style continuous loop. */
  indeterminate?: boolean;
  /** Diameter in px. */
  size?: number | string;
  /** Stroke width in px. */
  width?: number | string;
  /** Tone keyword / legacy `romm-*` / any CSS colour. */
  color?: string;
  /** 0–100. Only consulted when `indeterminate` is false. */
  modelValue?: number;
}

const props = withDefaults(defineProps<Props>(), {
  indeterminate: true,
  size: 24,
  width: 2,
  color: "primary",
  modelValue: undefined,
});

const slots = useSlots();

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

function toNumber(v: number | string, fallback: number): number {
  if (typeof v === "number") return v;
  if (typeof v === "string" && /^\d+(\.\d+)?$/.test(v)) return Number(v);
  return fallback;
}

const diameter = computed(() => toNumber(props.size, 24));
const strokeWidth = computed(() => toNumber(props.width, 2));
const radius = computed(() => (diameter.value - strokeWidth.value) / 2);

// Clamp 0–100, gracefully handles undefined.
const progressValue = computed<number>(() => {
  const v = props.modelValue;
  if (v === undefined || v === null) return 0;
  return Math.max(0, Math.min(100, v));
});

// With pathLength=100, dash values are percentages of the circle:
//   dasharray="100"  → reserve 100% of the path for the visible stroke
//   dashoffset       → hide N% from the start (= empty portion)
const dashOffset = computed(() => 100 - progressValue.value);
</script>

<template>
  <span
    v-bind="$attrs"
    class="r-pc"
    :class="{
      'r-pc--indeterminate': indeterminate,
      'r-pc--determinate': !indeterminate,
    }"
    :style="{
      width: `${diameter}px`,
      height: `${diameter}px`,
      '--r-pc-color': resolvedColor,
    }"
    role="progressbar"
    :aria-valuemin="0"
    :aria-valuemax="100"
    :aria-valuenow="indeterminate ? undefined : progressValue"
    :aria-busy="indeterminate || undefined"
  >
    <svg class="r-pc__svg" :viewBox="`0 0 ${diameter} ${diameter}`">
      <!-- Track — faint underlay so the empty portion still reads
           against complex backgrounds. Hidden under indeterminate. -->
      <circle
        class="r-pc__track"
        :cx="diameter / 2"
        :cy="diameter / 2"
        :r="radius"
        :stroke-width="strokeWidth"
        fill="none"
      />
      <!-- Arc — the visible progress / spinner snake. -->
      <circle
        class="r-pc__arc"
        :cx="diameter / 2"
        :cy="diameter / 2"
        :r="radius"
        :stroke-width="strokeWidth"
        fill="none"
        pathLength="100"
        :stroke-dasharray="indeterminate ? undefined : 100"
        :stroke-dashoffset="indeterminate ? undefined : dashOffset"
      />
    </svg>
    <span v-if="slots.default" class="r-pc__content">
      <slot />
    </span>
  </span>
</template>

<style scoped>
.r-pc {
  display: inline-flex;
  position: relative;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  /* `color` is the fallback for the arc — `--r-pc-color` overrides it
     so consumers can hand-roll a custom tone via inline style without
     touching the prop. */
  color: var(--r-pc-color);
  transition: color var(--r-motion-fast) var(--r-motion-ease-out);
}

.r-pc__svg {
  width: 100%;
  height: 100%;
  display: block;
  /* Start the arc at 12 o'clock — determinate progress reads as
     "fills clockwise from top" instead of "from 3 o'clock". */
  transform: rotate(-90deg);
  transform-origin: 50% 50%;
}

.r-pc__track {
  stroke: color-mix(in srgb, currentColor 18%, transparent);
}

.r-pc__arc {
  stroke: currentColor;
  stroke-linecap: round;
  /* Smooth the value swap so a determinate `modelValue` change reads
     as a fluid fill instead of jumping. The indeterminate path below
     disables this — two animation systems on the same property smear. */
  transition: stroke-dashoffset 320ms var(--r-motion-ease-out);
}

/* ── Indeterminate ─────────────────────────────────────────────── */

/* Two animations compose on the same SVG: the parent rotates linearly
   while the arc's dash cycles long→short→long. The combination is the
   Material-classic spinner — recognisable, smooth, GPU-friendly. */
.r-pc--indeterminate .r-pc__svg {
  animation: r-pc-rotate 1.6s linear infinite;
}
.r-pc--indeterminate .r-pc__arc {
  animation: r-pc-dash 1.4s ease-in-out infinite;
  transition: none;
}
.r-pc--indeterminate .r-pc__track {
  /* Hide the track for indeterminate — Material convention. The track
     only reads as "remaining capacity", which is meaningless during
     an unbounded loop. */
  display: none;
}

@keyframes r-pc-rotate {
  /* Start from the -90deg base (12 o'clock) and complete one full
     rotation per cycle. End value is `base + 360deg`. */
  from {
    transform: rotate(-90deg);
  }
  to {
    transform: rotate(270deg);
  }
}

@keyframes r-pc-dash {
  /* pathLength=100 → dash values are percentages of the circle. */
  0% {
    stroke-dasharray: 1, 100;
    stroke-dashoffset: 0;
  }
  50% {
    stroke-dasharray: 60, 100;
    stroke-dashoffset: -15;
  }
  100% {
    stroke-dasharray: 60, 100;
    stroke-dashoffset: -75;
  }
}

/* ── Content overlay — slot content centred over the ring ──────── */
.r-pc__content {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: var(--r-font-weight-semibold);
  color: var(--r-pc-color);
  line-height: 1;
  /* Scale the slot text with the ring — `cqi` (container-inline-size)
     would be ideal but isn't universally supported on SVG-adjacent
     containers; the static 11px works for most uses. Consumers can
     override via inline font-size. */
}

/* ── Reduced motion — drop the spinner animations ─────────────── */
@media (prefers-reduced-motion: reduce) {
  .r-pc--indeterminate .r-pc__svg,
  .r-pc--indeterminate .r-pc__arc {
    animation: none;
  }
  /* Show a static partial arc so the spinner still communicates "busy"
     without the rotation. */
  .r-pc--indeterminate .r-pc__arc {
    stroke-dasharray: 30, 100;
    stroke-dashoffset: 0;
  }
}
</style>
