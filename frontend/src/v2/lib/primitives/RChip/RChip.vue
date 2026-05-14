<script setup lang="ts">
// RChip — inline-flex pill / square label with prepend +
// append icons, optional close button, six variants, and the v2 size
// ladder.
//
// Visual vocabulary matches the rest of the lib: TONE_MAP for colours,
// translucent fills via `color-mix`, hover lift via opacity + scale.
// Clickable behaviour comes naturally — pass an `@click` listener via
// `$attrs` and the chip becomes a hit target (the hover transition
// already makes it feel interactive).
//
// `closable` renders an X button at the trailing edge that emits
// `click:close`. The close button stops propagation so chip clicks
// don't fire when the user is just dismissing it.
//
// `label` makes the chip square-cornered (mostly used for tags inline
// in lists). `rounded` overrides the default pill / label radius if
// you need a specific radius.
import { computed } from "vue";
import RIcon from "../RIcon/RIcon.vue";

defineOptions({ inheritAttrs: false });

interface Props {
  variant?: "flat" | "text" | "elevated" | "translucent" | "outlined" | "plain";
  color?: string;
  size?: "x-small" | "small" | "default" | "large" | "x-large";
  /** Square corners (small radius) — typical of inline metadata tags. */
  label?: boolean;
  /** Renders a trailing × button that emits `click:close`. */
  closable?: boolean;
  prependIcon?: string;
  appendIcon?: string;
  disabled?: boolean;
  /** Overrides the chip's default radius. `false`/`"0"` → square,
   *  `"full"`/`true` → pill (999px), `"sm"`/`"md"`/`"lg"`/`"xl"` →
   *  token radii, number → px. */
  rounded?: string | number | boolean;
}

const props = withDefaults(defineProps<Props>(), {
  variant: "translucent",
  color: undefined,
  size: "default",
  label: false,
  closable: false,
  prependIcon: undefined,
  appendIcon: undefined,
  disabled: false,
  rounded: undefined,
});

const emit = defineEmits<{
  (e: "click:close", evt: MouseEvent): void;
}>();

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
  if (r === undefined || r === null || r === "") {
    // Implicit: `label` → small radius, else pill.
    return props.label ? "4px" : "999px";
  }
  if (r === true) return "999px";
  if (r === false) return "0";
  if (typeof r === "number") return `${r}px`;
  if (/^\d+(\.\d+)?$/.test(r as string)) return `${r}px`;
  return ROUNDED_MAP[r as string] ?? String(r);
});

function onClose(evt: MouseEvent) {
  evt.stopPropagation();
  emit("click:close", evt);
}
</script>

<template>
  <span
    v-bind="$attrs"
    class="r-chip"
    :class="[
      `r-chip--${variant}`,
      `r-chip--${size}`,
      {
        'r-chip--has-color': !!resolvedColor,
        'r-chip--label': label,
        'r-chip--disabled': disabled,
      },
    ]"
    :style="{
      '--r-chip-color': resolvedColor,
      borderRadius: resolvedRounded,
    }"
    :aria-disabled="disabled || undefined"
  >
    <RIcon
      v-if="prependIcon"
      :icon="prependIcon"
      class="r-chip__icon r-chip__icon--prepend"
    />
    <span class="r-chip__content">
      <slot />
    </span>
    <RIcon
      v-if="appendIcon"
      :icon="appendIcon"
      class="r-chip__icon r-chip__icon--append"
    />
    <button
      v-if="closable"
      type="button"
      class="r-chip__close"
      aria-label="Remove"
      :disabled="disabled"
      @click="onClose"
    >
      <RIcon icon="mdi-close" class="r-chip__close-icon" />
    </button>
  </span>
</template>

<style scoped>
.r-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  white-space: nowrap;
  font-weight: var(--r-font-weight-medium);
  line-height: 1;
  border: 1px solid transparent;
  user-select: none;
  /* Subtle rest-state mute that brightens on hover — same idiom RBtn
     uses so chips and buttons share the rest-→-hover feel. Applied to
     every variant so non-interactive tag chips also feel "alive" when
     the cursor crosses them. */
  opacity: 0.85;
  transition:
    background var(--r-motion-fast) var(--r-motion-ease-out),
    color var(--r-motion-fast) var(--r-motion-ease-out),
    border-color var(--r-motion-fast) var(--r-motion-ease-out),
    box-shadow var(--r-motion-fast) var(--r-motion-ease-out),
    opacity var(--r-motion-fast) var(--r-motion-ease-out),
    transform var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-chip:hover:not(.r-chip--disabled) {
  opacity: 1;
}

.r-chip--disabled {
  opacity: 0.45;
  pointer-events: none;
}

.r-chip__content {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
}

.r-chip__icon {
  color: inherit;
  flex-shrink: 0;
}

/* ── Size ladder — height + horizontal padding + font-size ─────── */
.r-chip--x-small {
  height: 20px;
  padding: 0 8px;
  font-size: 10px;
  gap: 4px;
}
.r-chip--x-small .r-chip__icon {
  font-size: 12px;
}

.r-chip--small {
  height: 24px;
  padding: 0 10px;
  font-size: 11px;
  gap: 5px;
}
.r-chip--small .r-chip__icon {
  font-size: 14px;
}

.r-chip--default {
  height: 32px;
  padding: 0 14px;
  font-size: 13px;
  gap: 6px;
}
.r-chip--default .r-chip__icon {
  font-size: 16px;
}

.r-chip--large {
  height: 40px;
  padding: 0 18px;
  font-size: 15px;
  gap: 7px;
}
.r-chip--large .r-chip__icon {
  font-size: 18px;
}

.r-chip--x-large {
  height: 48px;
  padding: 0 22px;
  font-size: 16px;
  gap: 8px;
}
.r-chip--x-large .r-chip__icon {
  font-size: 20px;
}

/* When the chip starts with an icon, trim the leading padding so the
   icon sits at a consistent visual inset instead of disappearing
   behind the larger gap. */
.r-chip:has(.r-chip__icon--prepend) {
  padding-inline-start: 8px;
}
.r-chip:has(.r-chip__icon--append) {
  padding-inline-end: 8px;
}

/* ── Variant: flat (solid colour fill) ─────────────────────────── */
.r-chip--flat.r-chip--has-color {
  background: var(--r-chip-color);
  color: white;
}
.r-chip--flat:not(.r-chip--has-color) {
  background: var(--r-color-surface);
  color: var(--r-color-fg);
}

/* ── Variant: elevated (solid + drop shadow) ───────────────────── */
.r-chip--elevated.r-chip--has-color {
  background: var(--r-chip-color);
  color: white;
  box-shadow: 0 2px 6px color-mix(in srgb, black 24%, transparent);
}
.r-chip--elevated:not(.r-chip--has-color) {
  background: var(--r-color-surface);
  color: var(--r-color-fg);
  box-shadow: 0 2px 6px color-mix(in srgb, black 18%, transparent);
}

/* ── Variant: translucent (translucent + coloured text) ──────────────── */
.r-chip--translucent.r-chip--has-color {
  background: color-mix(in srgb, var(--r-chip-color) 16%, transparent);
  color: var(--r-chip-color);
}
.r-chip--translucent:not(.r-chip--has-color) {
  background: var(--r-color-surface);
  color: var(--r-color-fg-secondary);
}

/* ── Variant: outlined (border + transparent + coloured text) ──── */
.r-chip--outlined {
  background: transparent;
}
.r-chip--outlined.r-chip--has-color {
  color: var(--r-chip-color);
  border-color: color-mix(in srgb, var(--r-chip-color) 50%, transparent);
}
.r-chip--outlined:not(.r-chip--has-color) {
  color: var(--r-color-fg-secondary);
  border-color: var(--r-color-border);
}

/* ── Variant: text (no chrome, just coloured text) ─────────────── */
.r-chip--text {
  background: transparent;
}
.r-chip--text.r-chip--has-color {
  color: var(--r-chip-color);
}
.r-chip--text:not(.r-chip--has-color) {
  color: var(--r-color-fg-secondary);
}

/* ── Variant: plain (zero chrome, inherit everything) ──────────── */
.r-chip--plain {
  background: transparent;
  color: inherit;
}

/* ── Close button ──────────────────────────────────────────────── */
.r-chip__close {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: none;
  padding: 0;
  margin-inline-start: 4px;
  margin-inline-end: -2px;
  color: inherit;
  cursor: pointer;
  border-radius: 50%;
  width: 1.4em;
  height: 1.4em;
  /* The X grows + brightens on hover — micro feedback so the user
     knows the close button is interactive on its own, separately from
     the chip body. */
  opacity: 0.6;
  transition:
    opacity var(--r-motion-fast) var(--r-motion-ease-out),
    background var(--r-motion-fast) var(--r-motion-ease-out),
    transform var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-chip__close:hover {
  opacity: 1;
  background: color-mix(in srgb, currentColor 12%, transparent);
}
.r-chip__close:active {
  transform: scale(0.9);
}
.r-chip__close:disabled {
  cursor: not-allowed;
  opacity: 0.4;
}
.r-chip__close-icon {
  font-size: 0.85em;
}
</style>
