<script setup lang="ts">
// RToolbar — horizontal flex bar with four ordered
// regions: `prepend → title → default → append`. Designed for app
// bars, gallery headers, dialog title rows — anywhere you want a
// header strip that holds a label on the left and actions on the
// right.
//
// `flat` removes the bottom hairline (default look has one so the
// toolbar reads as a distinct surface above the content below).
// `color` paints the bar in a tone (white text); otherwise the bar
// uses the page's elevated bg.
//
// `height` is an explicit override. Without it the height is driven
// by the density ladder (48 / 56 / 64 px).
import { computed, useSlots } from "vue";

defineOptions({ inheritAttrs: false });

interface Props {
  /** Background tone — keyword / `romm-*` / any CSS colour. */
  color?: string;
  density?: "default" | "comfortable" | "compact";
  /** Drops the bottom border. */
  flat?: boolean;
  /** Auto-rendered title text — slot `#title` overrides. */
  title?: string;
  /** Explicit height override (number → px / any CSS length). */
  height?: number | string;
  rounded?: string | number | boolean;
}

const props = withDefaults(defineProps<Props>(), {
  color: undefined,
  density: "default",
  flat: false,
  title: undefined,
  height: undefined,
  rounded: undefined,
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
};
const resolvedRounded = computed<string | undefined>(() => {
  const r = props.rounded;
  if (r === undefined || r === null || r === "") return undefined;
  if (r === true) return "999px";
  if (r === false) return "0";
  if (typeof r === "number") return `${r}px`;
  if (/^\d+(\.\d+)?$/.test(r as string)) return `${r}px`;
  return ROUNDED_MAP[r as string] ?? String(r);
});

const resolvedHeight = computed<string | undefined>(() => {
  const h = props.height;
  if (h === undefined || h === null || h === "") return undefined;
  if (typeof h === "number") return `${h}px`;
  if (/^\d+(\.\d+)?$/.test(h as string)) return `${h}px`;
  return String(h);
});
</script>

<template>
  <div
    v-bind="$attrs"
    class="r-toolbar"
    :class="[
      `r-toolbar--density-${density}`,
      {
        'r-toolbar--has-color': !!resolvedColor,
        'r-toolbar--flat': flat,
      },
    ]"
    :style="{
      height: resolvedHeight,
      borderRadius: resolvedRounded,
      '--r-toolbar-color': resolvedColor,
    }"
    role="toolbar"
  >
    <!-- Prepend region (icons, back button, drawer toggle…). -->
    <span v-if="slots.prepend" class="r-toolbar__prepend">
      <slot name="prepend" />
    </span>

    <!-- Title — slot wins over prop. Title is given a min-width: 0 so
         long labels can ellipsis instead of pushing the action row off
         screen. -->
    <span v-if="title || slots.title" class="r-toolbar__title">
      <slot name="title">{{ title }}</slot>
    </span>

    <!-- Default slot — the "body". A horizontal spacer is appended
         after it so anything in `#append` floats to the right edge
         even when the default slot is empty. -->
    <span class="r-toolbar__body">
      <slot />
    </span>
    <span class="r-toolbar__spacer" aria-hidden="true" />

    <!-- Append region (action buttons, filters, sort dropdown…). -->
    <span v-if="slots.append" class="r-toolbar__append">
      <slot name="append" />
    </span>
  </div>
</template>

<style scoped>
.r-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  background: var(--r-toolbar-color, var(--r-color-bg-elevated));
  color: var(--r-color-fg);
  border-bottom: 1px solid var(--r-color-border);
  /* Smooth tone / theme swaps so a toolbar that changes colour mid-
     route doesn't pop. */
  transition:
    background var(--r-motion-fast) var(--r-motion-ease-out),
    border-color var(--r-motion-fast) var(--r-motion-ease-out),
    color var(--r-motion-fast) var(--r-motion-ease-out);
}

.r-toolbar--has-color {
  /* Coloured toolbars paint white text on top of the brand fill. */
  color: white;
}

.r-toolbar--flat {
  border-bottom-color: transparent;
}

/* ── Density — drives height + padding ───────────────────────── */
.r-toolbar--density-default {
  height: 64px;
  padding: 0 16px;
}
.r-toolbar--density-comfortable {
  height: 56px;
  padding: 0 14px;
}
.r-toolbar--density-compact {
  height: 48px;
  padding: 0 12px;
  gap: 10px;
}

/* On phones a 64px bar eats scarce vertical space. Trim the taller densities
   on `xs` (the explicit `height` prop still wins for consumers that pin a
   size; compact stays 48px). */
html[data-bp~="xs"] .r-toolbar--density-default {
  height: 56px;
}
html[data-bp~="xs"] .r-toolbar--density-comfortable {
  height: 52px;
}

/* ── Regions ──────────────────────────────────────────────────── */
.r-toolbar__prepend,
.r-toolbar__append {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}

.r-toolbar__title {
  /* Reasonable title weight without screaming. The `min-width: 0` is
     load-bearing: without it, a long title would push the body / append
     past the right edge instead of ellipsising. */
  font-size: 16px;
  font-weight: var(--r-font-weight-semibold);
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.r-toolbar__body {
  display: inline-flex;
  align-items: center;
  min-width: 0;
}

.r-toolbar__spacer {
  flex: 1 1 auto;
}
</style>
