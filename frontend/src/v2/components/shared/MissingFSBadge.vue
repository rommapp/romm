<script setup lang="ts">
// MissingFSBadge — tiny warning pill used in platform/ROM pickers to flag
// entries whose file is missing from disk. Replaces v1's
// `common/MissingFromFSIcon.vue` inside v2 contexts. Uses RTooltip so the
// tooltip styling matches the rest of v2.
import { RIcon, RTooltip } from "@v2/lib";

defineOptions({ inheritAttrs: false });

withDefaults(
  defineProps<{
    text: string;
    size?: number;
  }>(),
  {
    size: 14,
  },
);
</script>

<template>
  <span class="r-v2-missing-fs" role="img" :aria-label="text">
    <RTooltip :text="text" location="top" activator="parent" />
    <RIcon icon="mdi-folder-question" :size="size" />
  </span>
</template>

<style scoped>
.r-v2-missing-fs {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 3px 7px;
  background: color-mix(in srgb, var(--r-color-warning-fg) 14%, transparent);
  border: 1px solid
    color-mix(in srgb, var(--r-color-warning-fg) 30%, transparent);
  color: var(--r-color-warning-fg);
  border-radius: var(--r-radius-pill);
  line-height: 1;
}
</style>
