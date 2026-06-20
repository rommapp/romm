<script setup lang="ts">
// SettingsSection — the canonical section pattern used inside every
// settings view. Mirrors the mock's two-piece structure:
//
//   ┌─ header (small uppercase title + optional icon) ────┐
//   │ background tint, rounded-top corners only           │
//   ├─────────────────────────────────────────────────────┤
//   │ body (slot)                                         │
//   │ rounded-bottom corners, hairline-divided field rows │
//   └─────────────────────────────────────────────────────┘
//
// The body slot is the consumer's responsibility; common shapes are:
//   • SettingsField rows (one per labeled control), or
//   • a custom block (theme picker grid, provider grid, table).
// The component takes no opinion — it just provides the chrome.
import { RIcon } from "@v2/lib";

defineOptions({ inheritAttrs: false });

defineProps<{
  title: string;
  icon?: string;
}>();
</script>

<template>
  <section class="r-v2-settings-section">
    <header class="r-v2-settings-section__header">
      <RIcon v-if="icon" :icon="icon" size="14" />
      <span class="r-v2-settings-section__title">{{ title }}</span>
      <slot name="header-actions" />
    </header>
    <div class="r-v2-settings-section__body">
      <slot />
    </div>
  </section>
</template>

<style scoped>
.r-v2-settings-section {
  display: block;
}

.r-v2-settings-section__header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  background: var(--r-color-surface);
  border: 1px solid var(--r-color-border);
  border-bottom: none;
  border-radius: 10px 10px 0 0;
  color: var(--r-color-fg-muted);
}

.r-v2-settings-section__title {
  font-size: 11px;
  font-weight: var(--r-font-weight-bold);
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--r-color-fg-secondary);
  flex: 1;
  min-width: 0;
}

.r-v2-settings-section__body {
  border: 1px solid var(--r-color-border);
  border-radius: 0 0 10px 10px;
  overflow: hidden;
  background: var(--r-color-bg-elevated);
}
</style>
