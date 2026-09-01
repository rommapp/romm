<script setup lang="ts">
// Tile — the square card used by the Home dashboard's platform row, the
// /platforms grid, and the Jukebox's launch tiles.
import { computed } from "vue";
import type { RouteLocationRaw } from "vue-router";

defineOptions({ inheritAttrs: false });

const props = withDefaults(
  defineProps<{
    /** Renders a router-link when set, a button otherwise. */
    to?: RouteLocationRaw;
    /** `comfortable` for platform tiles, `compact` for the jukebox's. */
    density?: "comfortable" | "compact";
    /** Fixed-width tile for horizontal card rows. */
    row?: boolean;
    focusKey?: string;
  }>(),
  { to: undefined, density: "comfortable", row: true, focusKey: undefined },
);

const emit = defineEmits<{ (e: "click", event: MouseEvent): void }>();

const tag = computed(() => (props.to ? "router-link" : "button"));
</script>

<template>
  <component
    :is="tag"
    :to="to"
    :type="to ? undefined : 'button'"
    v-bind="$attrs"
    class="r-v2-tile"
    :class="[`r-v2-tile--${density}`, { 'r-v2-tile--row': row }]"
    :data-focus-key="focusKey"
    @click="emit('click', $event)"
  >
    <div class="r-v2-tile__icon"><slot name="icon" /></div>
    <slot name="badge" />
    <div class="r-v2-tile__name"><slot /></div>
    <div v-if="$slots.count" class="r-v2-tile__count">
      <slot name="count" />
    </div>
  </component>
</template>

<style scoped>
.r-v2-tile {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  appearance: none;
  min-width: 0;
  background: var(--r-color-bg-elevated);
  border: 1px solid var(--r-color-border);
  border-radius: var(--r-radius-card);
  color: var(--r-color-fg-secondary);
  text-decoration: none;
  cursor: pointer;
  transition:
    background var(--r-motion-fast),
    border-color var(--r-motion-fast),
    transform var(--r-motion-fast);
}

.r-v2-tile--row {
  width: 150px;
  flex: 0 0 150px;
}

.r-v2-tile--comfortable {
  gap: 12px;
  padding: 24px 16px 18px;
}

.r-v2-tile--compact {
  gap: 7px;
  padding: 14px 12px 12px;
}

/* Hover is gated to mouse/touch modality so a cursor parked from a
   previous mouse session doesn't compete with the focused tile when the
   user is driving with a gamepad. Focus-visible reads in every modality
   (subject to global.css's outline rules). */
html[data-input="mouse"] .r-v2-tile:hover,
html[data-input="touch"] .r-v2-tile:hover,
.r-v2-tile:focus-visible {
  background: var(--r-color-surface);
  border-color: var(--r-color-border-strong);
}

/* Keyboard / gamepad focus — stronger border + stacked brand glow so
   the focused tile reads distinctly from a hover. */
.r-v2-tile:focus-visible {
  border-color: var(--r-color-brand-primary);
  box-shadow:
    0 8px 28px color-mix(in srgb, black 35%, transparent),
    0 0 0 2px var(--r-color-brand-primary),
    0 0 18px color-mix(in srgb, var(--r-color-brand-primary) 55%, transparent);
  outline: none;
}

.r-v2-tile__icon {
  display: grid;
  place-items: center;
  color: var(--r-color-fg-heading);
  opacity: 0.9;
  transition:
    opacity var(--r-motion-fast),
    transform var(--r-motion-fast);
}

.r-v2-tile--comfortable .r-v2-tile__icon {
  width: 72px;
  height: 72px;
}

.r-v2-tile--compact .r-v2-tile__icon {
  width: 52px;
  height: 52px;
}

html[data-input="mouse"] .r-v2-tile:hover .r-v2-tile__icon,
html[data-input="touch"] .r-v2-tile:hover .r-v2-tile__icon,
.r-v2-tile:focus-visible .r-v2-tile__icon {
  opacity: 1;
  transform: scale(1.05);
}

.r-v2-tile__name {
  display: grid;
  place-items: center;
  font-size: 12px;
  font-weight: var(--r-font-weight-semibold);
  line-height: 1.35;
  text-align: center;
}

.r-v2-tile--compact .r-v2-tile__name {
  min-height: 32px;
}

.r-v2-tile__count {
  font-size: 11px;
  color: var(--r-color-fg-muted);
}

.r-v2-tile--compact .r-v2-tile__count {
  margin-top: auto;
}

html[data-bp~="xs"] .r-v2-tile--row {
  width: 110px;
  flex-basis: 110px;
}

html[data-bp~="xs"] .r-v2-tile--comfortable {
  padding: 12px 8px 10px;
  gap: 6px;
}

html[data-bp~="xs"] .r-v2-tile--compact {
  padding: 8px;
  gap: 4px;
}

html[data-bp~="xs"] .r-v2-tile__icon {
  width: 52px;
  height: 52px;
}

html[data-bp~="xs"] .r-v2-tile__name {
  font-size: 10px;
}

html[data-bp~="xs"] .r-v2-tile--compact .r-v2-tile__name {
  min-height: 28px;
}

html[data-bp~="xs"] .r-v2-tile__count {
  font-size: 9px;
}
</style>
