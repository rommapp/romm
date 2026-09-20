<script setup lang="ts">
// When an asset was last written: relative first, the exact moment under it.
import { useI18n } from "vue-i18n";
import { formatRelativeDate, formatTimestamp } from "@/utils";

defineOptions({ inheritAttrs: false });

withDefaults(defineProps<{ date: string; align?: "start" | "end" }>(), {
  align: "start",
});

const { locale } = useI18n();
</script>

<template>
  <span
    class="r-asset-timestamp"
    :class="`r-asset-timestamp--${align}`"
    v-bind="$attrs"
  >
    <span class="r-asset-timestamp__relative">
      {{ formatRelativeDate(date) }}
    </span>
    <span class="r-asset-timestamp__exact">
      {{ formatTimestamp(date, locale) }}
    </span>
  </span>
</template>

<style scoped>
.r-asset-timestamp {
  display: flex;
  flex-direction: column;
  gap: 2px;
  flex-shrink: 0;
  min-width: 0;
}
.r-asset-timestamp--end {
  align-items: flex-end;
}
.r-asset-timestamp__relative {
  font-size: 11px;
  font-weight: var(--r-font-weight-medium);
  color: var(--r-color-fg-secondary);
}
.r-asset-timestamp__exact {
  font-size: 10px;
  color: var(--r-color-fg-muted);
  font-variant-numeric: tabular-nums;
}

/* On a phone the exact moment is the first thing to go; tooltips keep it. */
html[data-bp~="xs"] .r-asset-timestamp__exact {
  display: none;
}
</style>
