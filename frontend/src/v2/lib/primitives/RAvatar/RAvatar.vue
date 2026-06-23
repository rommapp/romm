<script setup lang="ts">
// RAvatar — inline-flex container holding one of three contents in
// priority order: `image` (renders an <img>), `icon` (renders an
// RIcon), or the default slot (initials / arbitrary content).
// `overflow: hidden` + the rounded radius clips the image to the
// avatar shape automatically — no per-image border-radius needed.
//
// `color` resolves through the same tone map RIcon uses (`"primary"` →
// `var(--r-color-brand-primary)` etc., legacy `romm-*` and CSS colours
// pass through). Pair with `variant` to control how the colour paints:
// solid fill, translucent, outlined, or text-only.
//
// `size` keyword ladder (`"small"`, `"large"`, …). The font-size of
// any text slot scales to ~40% of the avatar height — initials stay
// legible at every size without a per-size override.
import { computed } from "vue";
import RIcon from "../RIcon/RIcon.vue";

defineOptions({ inheritAttrs: false });

interface Props {
  size?: string | number;
  color?: string;
  image?: string;
  icon?: string;
  /** `false | "0"` → square; `"sm" | "md" | "lg" | "xl"` → token radii;
   *  `"pill"` → fully pilled; `"circle" | true | undefined` → circle;
   *  number / px-length → raw value. */
  rounded?: string | number | boolean;
  variant?: "flat" | "elevated" | "translucent" | "outlined" | "text" | "plain";
}

const props = withDefaults(defineProps<Props>(), {
  size: "default",
  color: undefined,
  image: undefined,
  icon: undefined,
  rounded: undefined,
  variant: "flat",
});

const SIZE_MAP: Record<string, string> = {
  "x-small": "24px",
  small: "32px",
  default: "40px",
  large: "48px",
  "x-large": "56px",
};

const resolvedSize = computed<string>(() => {
  const s = props.size;
  if (s === undefined || s === null || s === "") return SIZE_MAP.default;
  if (typeof s === "number") return `${s}px`;
  if (/^\d+(\.\d+)?$/.test(s)) return `${s}px`;
  return SIZE_MAP[s] ?? s;
});

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
  pill: "999px",
  circle: "50%",
};

const resolvedRounded = computed<string>(() => {
  const r = props.rounded;
  // Default is circle.
  if (r === undefined || r === null) return "50%";
  if (r === true) return "50%";
  if (r === false) return "0";
  if (typeof r === "number") return `${r}px`;
  if (/^\d+(\.\d+)?$/.test(r)) return `${r}px`;
  return ROUNDED_MAP[r] ?? r;
});

// Font-size scales proportionally to the avatar's pixel height so the
// default slot (initials) stays legible at every size without callers
// computing per-size CSS. 40% of height is the sweet spot — matches
// the visual mass of v1's user avatars.
const fontSize = computed(() => {
  const px = parseFloat(resolvedSize.value);
  return Number.isFinite(px) ? `${Math.round(px * 0.4)}px` : "14px";
});

const styleObj = computed(() => ({
  width: resolvedSize.value,
  height: resolvedSize.value,
  borderRadius: resolvedRounded.value,
  fontSize: fontSize.value,
  // Variants read this var for their fills / borders / text colours.
  // Stays `undefined` when no `color` prop is set, falling through to
  // the variant's neutral defaults below.
  "--r-avatar-color": resolvedColor.value,
}));
</script>

<template>
  <div
    v-bind="$attrs"
    class="r-avatar"
    :class="[
      `r-avatar--${variant}`,
      { 'r-avatar--has-color': !!resolvedColor },
    ]"
    :style="styleObj"
  >
    <img v-if="image" :src="image" alt="" class="r-avatar__image" />
    <RIcon v-else-if="icon" :icon="icon" class="r-avatar__icon" />
    <slot v-else />
  </div>
</template>

<style scoped>
.r-avatar {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  flex-shrink: 0;
  position: relative;
  line-height: 1;
  font-weight: var(--r-font-weight-semibold);
  user-select: none;
  /* Smooth tone / theme swaps so the avatar pops in without flicker. */
  transition:
    background var(--r-motion-fast) var(--r-motion-ease-out),
    color var(--r-motion-fast) var(--r-motion-ease-out),
    box-shadow var(--r-motion-fast) var(--r-motion-ease-out),
    border-color var(--r-motion-fast) var(--r-motion-ease-out);
}

/* Image fills the container; `overflow: hidden` on the parent clips
   it to the rounded shape, no per-image radius needed. */
.r-avatar__image {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

/* Icon scales to the avatar's font-size so a 24px avatar renders a
   small icon and a 56px avatar renders a big one — no caller maths. */
.r-avatar__icon {
  font-size: 1.2em;
  color: inherit;
}

/* ── Variant: flat — solid colour fill ─────────────────────────── */
.r-avatar--flat.r-avatar--has-color {
  background: var(--r-avatar-color);
  color: white;
}
.r-avatar--flat:not(.r-avatar--has-color) {
  background: var(--r-color-surface);
  color: var(--r-color-fg);
}

/* ── Variant: elevated — solid fill + soft shadow ──────────────── */
.r-avatar--elevated.r-avatar--has-color {
  background: var(--r-avatar-color);
  color: white;
  box-shadow: 0 2px 8px color-mix(in srgb, black 30%, transparent);
}
.r-avatar--elevated:not(.r-avatar--has-color) {
  background: var(--r-color-surface);
  color: var(--r-color-fg);
  box-shadow: 0 2px 8px color-mix(in srgb, black 20%, transparent);
}

/* ── Variant: translucent — soft tinted fill, coloured text ────── */
.r-avatar--translucent.r-avatar--has-color {
  background: color-mix(in srgb, var(--r-avatar-color) 18%, transparent);
  color: var(--r-avatar-color);
}
.r-avatar--translucent:not(.r-avatar--has-color) {
  background: var(--r-color-surface);
  color: var(--r-color-fg);
}

/* ── Variant: outlined — border + coloured text ────────────────── */
.r-avatar--outlined {
  background: transparent;
}
.r-avatar--outlined.r-avatar--has-color {
  color: var(--r-avatar-color);
  border: 1px solid var(--r-avatar-color);
}
.r-avatar--outlined:not(.r-avatar--has-color) {
  color: var(--r-color-fg);
  border: 1px solid var(--r-color-border);
}

/* ── Variant: text — no fill, just coloured glyph/initial ──────── */
.r-avatar--text {
  background: transparent;
}
.r-avatar--text.r-avatar--has-color {
  color: var(--r-avatar-color);
}
.r-avatar--text:not(.r-avatar--has-color) {
  color: var(--r-color-fg);
}

/* ── Variant: plain — fully unstyled (inherit everything) ──────── */
.r-avatar--plain {
  background: transparent;
  color: inherit;
}
</style>
