<script setup lang="ts">
// BreakpointBadge — dev-only overlay showing the active responsive tier
// and live viewport width. Mounted by AppLayout but only rendered when
// `import.meta.env.DEV`, so it carries zero production cost. Makes the
// manual responsive sweep faster: you always see which `data-bp` tier is
// active without opening devtools. Reads the same `useBreakpoint()` refs
// that drive `<html data-bp>`, so it can never drift from the real state.
import { useWindowSize } from "@vueuse/core";
import { computed } from "vue";
import { useBreakpoint } from "@/v2/composables/useBreakpoint";

const isDev = import.meta.env.DEV;

const { xs, smAndUp, mdAndUp, lgAndUp, xlAndUp } = useBreakpoint();
const { width } = useWindowSize();

// Largest active tier — the single name a designer thinks in.
const tier = computed(() => {
  if (xlAndUp.value) return "xl";
  if (lgAndUp.value) return "lg";
  if (mdAndUp.value) return "md";
  if (smAndUp.value) return "sm";
  if (xs.value) return "xs";
  return "—";
});
</script>

<template>
  <div v-if="isDev" class="r-v2-bp-badge" aria-hidden="true">
    <span class="r-v2-bp-badge__tier">{{ tier }}</span>
    <span class="r-v2-bp-badge__w">{{ Math.round(width) }}px</span>
  </div>
</template>

<style scoped>
.r-v2-bp-badge {
  position: fixed;
  bottom: 8px;
  left: 8px;
  z-index: var(--r-z-snackbar);
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 3px 8px;
  border-radius: var(--r-radius-pill);
  background: var(--r-color-panel);
  border: 1px solid var(--r-color-panel-border);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  font-family: var(--r-font-family-mono);
  font-size: var(--r-font-size-xs);
  line-height: 1;
  color: var(--r-color-fg-secondary);
  pointer-events: none;
  user-select: none;
  opacity: 0.7;
}

.r-v2-bp-badge__tier {
  font-weight: var(--r-font-weight-bold);
  color: var(--r-color-brand-primary);
  text-transform: uppercase;
}
</style>
