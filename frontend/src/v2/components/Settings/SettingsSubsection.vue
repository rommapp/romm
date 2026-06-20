<script setup lang="ts">
// SettingsSubsection — a lighter heading used inside a SettingsSection's
// body when the section logically contains related groups (e.g. Home →
// Widgets). Reads as a divider + small uppercase label so the visual
// hierarchy stays clear without nesting another full section card.
import { RIcon } from "@v2/lib";

defineOptions({ inheritAttrs: false });

defineProps<{
  title: string;
  icon?: string;
}>();
</script>

<template>
  <div class="r-v2-settings-sub">
    <div class="r-v2-settings-sub__head">
      <RIcon v-if="icon" :icon="icon" size="12" />
      <span class="r-v2-settings-sub__title">{{ title }}</span>
      <slot name="header-actions" />
    </div>
    <div class="r-v2-settings-sub__body">
      <slot />
    </div>
  </div>
</template>

<style scoped>
.r-v2-settings-sub {
  display: flex;
  flex-direction: column;
  /* Hairline divider above each subsection so adjacent subsections
     read as siblings inside the same section card. The section's own
     body fields paint their own dividers; this matches that rhythm. */
  border-top: 1px solid var(--r-color-border);
}
.r-v2-settings-sub:first-child {
  border-top: 0;
}

.r-v2-settings-sub__head {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px 4px;
  color: var(--r-color-fg-muted);
}

.r-v2-settings-sub__title {
  font-size: 10.5px;
  font-weight: var(--r-font-weight-bold);
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--r-color-fg-muted);
  flex: 1;
  min-width: 0;
}

.r-v2-settings-sub__body {
  display: flex;
  flex-direction: column;
}
</style>
