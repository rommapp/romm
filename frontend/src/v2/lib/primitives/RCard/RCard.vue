<script setup lang="ts">
// RCard — plain surface container with six variants, a thin loading
// bar, optional title / subtitle header, and the shared rounded /
// tone / elevation resolvers from the rest of the lib.
//
// No default padding — RCard keeps its body slot raw; pad from outside
// or wrap an inner `<div>` (the `auth-card__inner` /
// `r-v2-ejs__panel-head` patterns already do this).
//
// Variants:
//   • flat        — surface fill + 1px border. The default — matches
//                   the existing v2 card paint.
//   • elevated    — surface fill + box-shadow (no border).
//   • translucent — `color-mix` of the resolved colour over transparent.
//   • outlined    — transparent fill + 1px coloured border.
//   • text        — transparent fill, just a tone colour for the text.
//   • plain       — zero chrome; inherit everything.
//
// `elevation` (0–24) maps to discrete box-shadow steps. Off-key values
// snap down to the nearest tabulated step so a card stays in the
// design system even if a consumer passes 5 or 9.
import { computed, useSlots } from "vue";

defineOptions({ inheritAttrs: false });

interface Props {
  variant?: "flat" | "elevated" | "translucent" | "outlined" | "text" | "plain";
  color?: string;
  elevation?: number | string;
  rounded?: string | number | boolean;
  title?: string;
  subtitle?: string;
  /** Thin animated bar at the top of the card — indicator that the
   *  card's content is updating in place. */
  loading?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
  variant: "flat",
  color: undefined,
  elevation: undefined,
  rounded: "lg",
  title: undefined,
  subtitle: undefined,
  loading: false,
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

const resolvedColor = computed<string | undefined>(() => {
  const c = props.color;
  if (!c) return undefined;
  return TONE_MAP[c] ?? c;
});

const ROUNDED_MAP: Record<string, string> = {
  "0": "0",
  sm: "4px",
  md: "8px",
  lg: "12px",
  xl: "16px",
  full: "999px",
  pill: "999px",
  circle: "50%",
};

const resolvedRounded = computed<string>(() => {
  const r = props.rounded;
  if (r === undefined || r === null || r === "") return "12px";
  if (r === true) return "999px";
  if (r === false) return "0";
  if (typeof r === "number") return `${r}px`;
  if (/^\d+(\.\d+)?$/.test(r as string)) return `${r}px`;
  return ROUNDED_MAP[r as string] ?? String(r);
});

// Elevation map — discrete shadow steps. Off-key values snap down to
// the nearest tabulated step so a stray `elevation=5` still lands on
// a system-approved shadow instead of a unique one-off.
const ELEVATION_MAP: Record<number, string> = {
  0: "none",
  1: "0 1px 2px color-mix(in srgb, black 14%, transparent)",
  2: "0 2px 4px color-mix(in srgb, black 16%, transparent)",
  4: "0 4px 10px color-mix(in srgb, black 20%, transparent)",
  6: "0 6px 14px color-mix(in srgb, black 22%, transparent)",
  8: "0 8px 18px color-mix(in srgb, black 26%, transparent)",
  12: "0 12px 26px color-mix(in srgb, black 28%, transparent)",
  16: "0 14px 30px color-mix(in srgb, black 30%, transparent)",
  24: "0 18px 36px color-mix(in srgb, black 35%, transparent)",
};
const ELEVATION_KEYS = Object.keys(ELEVATION_MAP)
  .map(Number)
  .sort((a, b) => a - b);

const resolvedElevation = computed<string | undefined>(() => {
  const e = props.elevation;
  if (e === undefined || e === null) return undefined;
  const n = typeof e === "number" ? e : Number(e);
  if (!Number.isFinite(n)) return undefined;
  if (n <= 0) return ELEVATION_MAP[0];
  // Snap down to the largest tabulated key ≤ n.
  let best = ELEVATION_KEYS[0];
  for (const k of ELEVATION_KEYS) {
    if (k <= n) best = k;
  }
  return ELEVATION_MAP[best];
});

const hasHeader = computed(
  () => !!props.title || !!props.subtitle || !!slots.title || !!slots.subtitle,
);
</script>

<template>
  <div
    v-bind="$attrs"
    class="r-card"
    :class="[
      `r-card--${variant}`,
      {
        'r-card--has-color': !!resolvedColor,
        'r-card--loading': loading,
      },
    ]"
    :style="{
      borderRadius: resolvedRounded,
      boxShadow: resolvedElevation,
      '--r-card-color': resolvedColor,
    }"
  >
    <!-- Loading bar at the top. The bar lives inside the card so it
         clips to the rounded corners cleanly. -->
    <div v-if="loading" class="r-card__loading" aria-hidden="true">
      <span class="r-card__loading-bar" />
    </div>

    <!-- Optional title / subtitle header. Slots win over props when
         the consumer wants richer content. -->
    <div v-if="hasHeader" class="r-card__header">
      <div v-if="title || slots.title" class="r-card__title">
        <slot name="title">{{ title }}</slot>
      </div>
      <div v-if="subtitle || slots.subtitle" class="r-card__subtitle">
        <slot name="subtitle">{{ subtitle }}</slot>
      </div>
    </div>

    <slot />
  </div>
</template>

<style scoped>
.r-card {
  position: relative;
  display: block;
  color: var(--r-color-fg);
  overflow: hidden;
  /* Smooth tone / theme / elevation changes so a swap doesn't pop. */
  transition:
    background var(--r-motion-fast) var(--r-motion-ease-out),
    border-color var(--r-motion-fast) var(--r-motion-ease-out),
    box-shadow var(--r-motion-base) var(--r-motion-ease-out),
    color var(--r-motion-fast) var(--r-motion-ease-out);
}

/* ── Variant: flat — surface + 1px border (the v2 default look) ── */
.r-card--flat {
  background: var(--r-color-bg-elevated);
  border: 1px solid var(--r-color-border);
}
.r-card--flat.r-card--has-color {
  background: var(--r-card-color);
  color: white;
  border-color: transparent;
}

/* ── Variant: elevated — surface + drop shadow, no border ─────── */
.r-card--elevated {
  background: var(--r-color-bg-elevated);
  border: 1px solid transparent;
  /* When `elevation` prop is unset we still want a baseline shadow so
     `elevated` reads different from `flat`. Inline `boxShadow` from
     the prop overrides this. */
  box-shadow: 0 4px 10px color-mix(in srgb, black 20%, transparent);
}
.r-card--elevated.r-card--has-color {
  background: var(--r-card-color);
  color: white;
}

/* ── Variant: translucent — color-mix tint, coloured text ─────── */
.r-card--translucent {
  border: 1px solid transparent;
}
.r-card--translucent.r-card--has-color {
  background: color-mix(in srgb, var(--r-card-color) 14%, transparent);
  color: var(--r-card-color);
}
.r-card--translucent:not(.r-card--has-color) {
  background: var(--r-color-surface);
  color: var(--r-color-fg);
}

/* ── Variant: outlined — transparent + border ──────────────────── */
.r-card--outlined {
  background: transparent;
}
.r-card--outlined.r-card--has-color {
  color: var(--r-card-color);
  border: 1px solid color-mix(in srgb, var(--r-card-color) 50%, transparent);
}
.r-card--outlined:not(.r-card--has-color) {
  border: 1px solid var(--r-color-border);
}

/* ── Variant: text — no chrome, just coloured text ─────────────── */
.r-card--text {
  background: transparent;
  border: 1px solid transparent;
}
.r-card--text.r-card--has-color {
  color: var(--r-card-color);
}

/* ── Variant: plain — fully unstyled ───────────────────────────── */
.r-card--plain {
  background: transparent;
  border: none;
  color: inherit;
}

/* ── Loading bar ───────────────────────────────────────────────── */
.r-card__loading {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 2px;
  overflow: hidden;
  background: color-mix(
    in srgb,
    var(--r-card-color, var(--r-color-brand-primary)) 22%,
    transparent
  );
  z-index: 1;
}
.r-card__loading-bar {
  position: absolute;
  inset: 0;
  background: var(--r-card-color, var(--r-color-brand-primary));
  /* Sliding bar from off-left to off-right. The 30% width keeps the
     bar readable without filling the whole track. */
  width: 30%;
  animation: r-card-loading 1.4s ease-in-out infinite;
}

/* Solid-tone variants paint the whole card in --r-card-color, so the
   bar/track must swap to currentColor (white on those variants) to
   stay visible — without this the loader vanishes into the background. */
.r-card--flat.r-card--has-color .r-card__loading,
.r-card--elevated.r-card--has-color .r-card__loading {
  background: color-mix(in srgb, currentColor 22%, transparent);
}
.r-card--flat.r-card--has-color .r-card__loading-bar,
.r-card--elevated.r-card--has-color .r-card__loading-bar {
  background: currentColor;
}

@keyframes r-card-loading {
  0% {
    transform: translateX(-100%);
  }
  100% {
    transform: translateX(400%);
  }
}

/* ── Header (title / subtitle) ─────────────────────────────────── */
.r-card__header {
  padding: 16px 20px 8px;
}
.r-card__title {
  font-size: var(--r-font-size-md, 15px);
  font-weight: var(--r-font-weight-semibold);
  line-height: 1.3;
}
.r-card__subtitle {
  margin-top: 4px;
  font-size: var(--r-font-size-sm, 12px);
  color: var(--r-color-fg-muted);
  line-height: 1.4;
}

/* When loading is on, push the header down a hair so the bar isn't
   pressed against the title — only when there's actually a header. */
.r-card--loading .r-card__header {
  padding-top: 18px;
}

/* ── Reduced motion — drop the loading slide ──────────────────── */
@media (prefers-reduced-motion: reduce) {
  .r-card__loading-bar {
    animation: none;
    width: 100%;
    opacity: 0.5;
  }
}
</style>
