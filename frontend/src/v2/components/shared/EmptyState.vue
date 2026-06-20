<script setup lang="ts">
// EmptyState — centered "nothing here" block used by index views and
// search results. Two visual variants depending on `variant`:
//   * "plain" — just a dim centered line of text (index views default)
//   * "boxed" — dashed-border elevated box with an mdi icon above the
//     message (Search view's "type to search" / "no matches")
import { RIcon } from "@v2/lib";

defineOptions({ inheritAttrs: false });

withDefaults(
  defineProps<{
    variant?: "plain" | "boxed";
    icon?: string;
    message?: string;
  }>(),
  { variant: "plain" },
);
</script>

<template>
  <div v-bind="$attrs" class="empty-state" :class="[`empty-state--${variant}`]">
    <RIcon v-if="icon" :icon="icon" size="36" class="empty-state__icon" />
    <slot>
      <p v-if="message" class="empty-state__msg">{{ message }}</p>
    </slot>
  </div>
</template>

<style scoped>
.empty-state {
  text-align: center;
}

.empty-state__icon {
  color: var(--r-color-fg-muted);
}

.empty-state__msg {
  margin: 0;
}

/* Plain — just dim centered text, for index views. */
.empty-state--plain {
  padding: 80px 16px;
  color: var(--r-color-fg-faint);
  font-size: 13.5px;
}
.empty-state--plain .empty-state__icon {
  display: block;
  margin: 0 auto var(--r-space-3);
}

/* Boxed — dashed-border elevated panel with optional icon above. */
.empty-state--boxed {
  padding: var(--r-space-10) var(--r-space-6);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--r-space-3);
  color: var(--r-color-fg-muted);
  background: var(--r-color-bg-elevated);
  border: 1px dashed var(--r-color-border);
  border-radius: var(--r-radius-md);
}
</style>
