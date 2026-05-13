<script setup lang="ts">
// RDivider — Vuetify-free. Three render modes:
//
//   • Horizontal plain — a block element with `border-top` (no inner
//     children; the border itself paints the line so the divider takes
//     zero height + zero baseline impact in a flex column).
//   • Vertical plain — same trick but `border-left` + `align-self:
//     stretch` so the divider matches its flex parent's cross-axis.
//   • With text (default slot present) — flex container with two
//     flex-grown line segments flanking the slot content. The "or"
//     pattern from Auth / inline section breaks.
//
// `inset` shifts the divider rightwards 72px to align with list-item
// text (matches Vuetify's `inset` semantics, kept for API parity even
// though no v2 surface uses it yet). `thickness` accepts a number (px)
// or any CSS length.
//
// Colour + font defaults live on the root so the consumer can recolour
// the divider + its text by setting `color` / `font-size` on the root
// from outside. Inner content uses `font: inherit; color: inherit;`
// to receive those overrides without `:deep()` hacks.
import { computed, useSlots } from "vue";

defineOptions({ inheritAttrs: false });

interface Props {
  vertical?: boolean;
  inset?: boolean;
  thickness?: number | string;
}

const props = withDefaults(defineProps<Props>(), {
  vertical: false,
  inset: false,
  thickness: undefined,
});

const slots = useSlots();
const hasText = computed(() => !!slots.default);

const resolvedThickness = computed<string | undefined>(() => {
  const t = props.thickness;
  if (t === undefined || t === null || t === "") return undefined;
  if (typeof t === "number") return `${t}px`;
  if (/^\d+(\.\d+)?$/.test(t)) return `${t}px`;
  return t;
});

// In plain mode the thickness controls the root's border-*-width; in
// with-text mode the borders don't exist (the line is a sibling div),
// so we instead style the `.r-divider__line` height/width.
const rootStyle = computed(() => {
  if (!resolvedThickness.value || hasText.value) return undefined;
  return props.vertical
    ? { borderLeftWidth: resolvedThickness.value }
    : { borderTopWidth: resolvedThickness.value };
});

const lineStyle = computed(() => {
  if (!resolvedThickness.value || !hasText.value) return undefined;
  return props.vertical
    ? { width: resolvedThickness.value }
    : { height: resolvedThickness.value };
});
</script>

<template>
  <div
    v-bind="$attrs"
    class="r-divider"
    :class="{
      'r-divider--vertical': vertical,
      'r-divider--horizontal': !vertical,
      'r-divider--inset': inset,
      'r-divider--with-text': hasText,
    }"
    :style="rootStyle"
    role="separator"
    :aria-orientation="vertical ? 'vertical' : 'horizontal'"
  >
    <template v-if="hasText">
      <span class="r-divider__line" :style="lineStyle" aria-hidden="true" />
      <span class="r-divider__content"><slot /></span>
      <span class="r-divider__line" :style="lineStyle" aria-hidden="true" />
    </template>
  </div>
</template>

<style scoped>
.r-divider {
  /* Defaults propagate to content via inheritance — overridable from
     the consumer side by setting `color` / `font-size` on the root. */
  color: var(--r-color-fg-muted);
  font-size: var(--r-font-size-xs);
  /* Smooth colour changes so a theme swap or hover doesn't pop. */
  transition: color var(--r-motion-fast) var(--r-motion-ease-out);
}

/* ── Plain (no slot) ───────────────────────────────────────────── */
.r-divider:not(.r-divider--with-text) {
  display: block;
}
.r-divider--horizontal:not(.r-divider--with-text) {
  width: 100%;
  height: 0;
  border-top: 1px solid var(--r-color-border);
}
.r-divider--vertical:not(.r-divider--with-text) {
  align-self: stretch;
  width: 0;
  border-left: 1px solid var(--r-color-border);
}

/* ── With text ─────────────────────────────────────────────────── */
.r-divider--with-text {
  display: flex;
  align-items: center;
}
.r-divider--horizontal.r-divider--with-text {
  flex-direction: row;
  width: 100%;
  gap: 12px;
}
.r-divider--vertical.r-divider--with-text {
  flex-direction: column;
  align-self: stretch;
  gap: 8px;
}

.r-divider__line {
  flex: 1 1 auto;
  background: var(--r-color-border);
  transition: background var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-divider--horizontal .r-divider__line {
  height: 1px;
}
.r-divider--vertical .r-divider__line {
  width: 1px;
}

.r-divider__content {
  flex-shrink: 0;
  font: inherit;
  color: inherit;
  letter-spacing: inherit;
}

/* ── Inset (list-style left margin) ────────────────────────────── */
.r-divider--inset.r-divider--horizontal {
  margin-inline-start: 72px;
}
</style>
