<script setup lang="ts">
// WidgetCard — shared shell for Home-page widget cards (the bar that
// sits above the dashboard rows). Owns chrome only: title, body slot,
// loading state, and an absolutely-positioned action slot for top-right
// affordances like the random-pick reroll button. Individual widgets
// (RandomPick, LibrarySnapshot, …) compose this with their own body.
import { RSpinner } from "@v2/lib";
import { useSlots } from "vue";

defineOptions({ inheritAttrs: false });

withDefaults(
  defineProps<{
    title: string;
    loading?: boolean;
    /** Card width — defaults to the mock's 220px. Wider widgets can
     *  override (e.g. Library Snapshot extended mode). */
    width?: string;
  }>(),
  {
    loading: false,
    width: "220px",
  },
);

const slots = useSlots();
</script>

<template>
  <div class="r-v2-widget" :style="{ width }">
    <div class="r-v2-widget__title">{{ title }}</div>
    <div v-if="slots.action" class="r-v2-widget__action">
      <slot name="action" />
    </div>
    <div v-if="loading" class="r-v2-widget__loading">
      <RSpinner :size="22" />
    </div>
    <slot v-else />
  </div>
</template>

<style scoped>
.r-v2-widget {
  flex-shrink: 0;
  /* Fixed height — every widget reads as part of the same rail, so
     they all share the same vertical footprint. Widgets that need
     more room (LibraryStats extended mode) grow horizontally (card
     `width` prop) rather than taller. Tuned to RandomPick's natural
     content (16 padding + 14 title + 8 gap + 70 cover + 16 padding
     = 124, rounded up so loading/loaded states match without a
     post-load pop). */
  height: 128px;
  background: var(--r-color-bg-elevated);
  border: 1px solid var(--r-color-border);
  border-radius: var(--r-radius-lg);
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  position: relative;
  overflow: hidden;
  box-sizing: border-box;
}

.r-v2-widget__title {
  font-size: 10.5px;
  font-weight: var(--r-font-weight-bold);
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--r-color-fg-muted);
}

.r-v2-widget__action {
  position: absolute;
  top: 10px;
  right: 10px;
}

.r-v2-widget__loading {
  display: flex;
  align-items: center;
  justify-content: center;
  flex: 1;
  opacity: 0.5;
}
</style>
