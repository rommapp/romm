<script setup lang="ts">
// RIcon — renders an MDI glyph via the `@mdi/font` CSS pseudo-element
// pipeline. `font-size` drives the visual size; `color` resolves either
// a v2 tone keyword (`"primary"`, `"success"`, …) or a legacy `romm-*`
// name, or passes through any CSS colour value (hex, rgb(...), named
// CSS colour). When `color` is omitted the icon inherits its parent.
//
// Sized via `font-size` (not `width`/`height`) because the glyph is a
// pseudo-element on the `.mdi` class. We mirror the icon's `font-size`
// to `width`/`height` so the wrapper is a perfect square — keeps icon
// + text alignment in flex rows tight.
import { computed } from "vue";

defineOptions({ inheritAttrs: false });

interface Props {
  /** MDI class name including the prefix, e.g. `mdi-controller`. */
  icon?: string;
  /** Named ladder (`x-small | small | default | large | x-large`),
   *  bare number (px), or any CSS length (`"1.4em"`, `"20px"`). */
  size?: string | number;
  /** v2 tone keyword, legacy `romm-*`, or any CSS colour. Omit to
   *  inherit the parent's text colour. */
  color?: string;
}

const props = withDefaults(defineProps<Props>(), {
  icon: undefined,
  size: undefined,
  color: undefined,
});

// Named size ladder so call sites pass `"small"` / `"large"` without
// rounding pixel values. Numeric sizes (`24`, `"24"`) are coerced to
// px; pre-formatted lengths pass through.
const SIZE_MAP: Record<string, string> = {
  "x-small": "12px",
  small: "16px",
  default: "24px",
  large: "36px",
  "x-large": "40px",
};

const resolvedSize = computed<string | undefined>(() => {
  const s = props.size;
  if (s === undefined || s === null || s === "") return undefined;
  if (typeof s === "number") return `${s}px`;
  if (/^\d+(\.\d+)?$/.test(s)) return `${s}px`;
  return SIZE_MAP[s] ?? s;
});

// Single source of truth for v2 tone aliasing. Other primitives will
// share this once we extract it.
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

const styleObj = computed(() => {
  const out: Record<string, string> = {};
  if (resolvedSize.value) {
    out.fontSize = resolvedSize.value;
    out.width = resolvedSize.value;
    out.height = resolvedSize.value;
  }
  if (resolvedColor.value) out.color = resolvedColor.value;
  return out;
});
</script>

<template>
  <i
    v-bind="$attrs"
    class="r-icon mdi"
    :class="icon"
    :style="styleObj"
    aria-hidden="true"
  >
    <slot />
  </i>
</template>

<style scoped>
.r-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  line-height: 1;
  /* Inherit colour from the parent unless overridden. Keeps icon +
     text colour locked together inside buttons / chips. */
  color: inherit;
  /* Smooth the glyph everywhere the OS will let us. Without these the
     icon looks slightly heavier on Windows / Linux. */
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  text-rendering: auto;
  user-select: none;
  /* Animate colour/transform changes so consumers that toggle tones
     (favourite, selected, error) get a smooth swap rather than a hard
     flip. Cheap, idempotent — matches the motion vocabulary RSwitch
     established. */
  transition:
    color var(--r-motion-fast) var(--r-motion-ease-out),
    transform var(--r-motion-fast) var(--r-motion-ease-out);
}
</style>
