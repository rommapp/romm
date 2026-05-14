<script setup lang="ts">
// RList — container for a vertical stack of RListItem
// children. Plays two roles:
//
//   • Semantic outer — wraps the items in `role="list"` so screen
//     readers announce the count + position regardless of how the
//     RListItem inner element is rendered (button / link / div).
//   • CSS context — emits `--r-list-item-h` and `--r-list-active-color`
//     custom properties that children inherit. Tweaking density or
//     active tone happens at the list, not on each item.
//
// `density` compresses item height. `color` drives the active highlight
// (defaults to brand-primary). `bgColor` paints the list's own surface
// — when set, the list reads as a self-contained card; otherwise it
// stays transparent and sits inside whatever parent paints around it.
import { computed } from "vue";

defineOptions({ inheritAttrs: false });

interface Props {
  density?: "default" | "comfortable" | "compact";
  rounded?: string | number | boolean;
  /** Tone for the active item highlight. */
  color?: string;
  /** Optional background paint for the list itself. */
  bgColor?: string;
}

const props = withDefaults(defineProps<Props>(), {
  density: "comfortable",
  rounded: "md",
  color: "primary",
  bgColor: undefined,
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

const resolvedColor = computed<string>(
  () => TONE_MAP[props.color] ?? props.color ?? TONE_MAP.primary,
);

const resolvedBg = computed<string | undefined>(() => {
  const b = props.bgColor;
  if (!b) return undefined;
  return TONE_MAP[b] ?? b;
});

const ROUNDED_MAP: Record<string, string> = {
  "0": "0",
  sm: "4px",
  md: "8px",
  lg: "12px",
  xl: "16px",
  full: "999px",
};
const resolvedRounded = computed<string>(() => {
  const r = props.rounded;
  if (r === undefined || r === null || r === "") return "8px";
  if (r === true) return "999px";
  if (r === false) return "0";
  if (typeof r === "number") return `${r}px`;
  if (/^\d+(\.\d+)?$/.test(r as string)) return `${r}px`;
  return ROUNDED_MAP[r as string] ?? String(r);
});
</script>

<template>
  <ul
    v-bind="$attrs"
    role="list"
    class="r-list"
    :class="[`r-list--density-${density}`]"
    :style="{
      borderRadius: resolvedRounded,
      background: resolvedBg,
      '--r-list-active-color': resolvedColor,
    }"
  >
    <slot />
  </ul>
</template>

<style scoped>
.r-list {
  list-style: none;
  margin: 0;
  padding: 4px;
  display: flex;
  flex-direction: column;
  gap: 2px;
  color: var(--r-color-fg);
  /* Default item height (CSS var children read). Density overrides
     below. Min-height — items can grow vertically when subtitle is
     present without touching this. */
  --r-list-item-h: 40px;
}

.r-list--density-default {
  --r-list-item-h: 48px;
}
.r-list--density-comfortable {
  --r-list-item-h: 40px;
}
.r-list--density-compact {
  --r-list-item-h: 32px;
  padding: 2px;
}
</style>
