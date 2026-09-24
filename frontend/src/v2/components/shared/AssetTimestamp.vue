<script setup lang="ts">
// When an asset was last written: the relative time beside the exact moment,
// or stacked flush right for a trailing time column.
import { useI18n } from "vue-i18n";
import { formatRelativeDate, formatTimestamp } from "@/utils";

defineOptions({ inheritAttrs: false });

withDefaults(defineProps<{ date: string; stacked?: boolean }>(), {
  stacked: false,
});

const { locale } = useI18n();
</script>

<template>
  <span
    class="r-asset-timestamp"
    :class="{ 'r-asset-timestamp--stacked': stacked }"
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
  flex-wrap: wrap;
  align-items: baseline;
  gap: 2px 6px;
  flex-shrink: 0;
  min-width: 0;
}
.r-asset-timestamp--stacked {
  flex-direction: column;
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
</style>
