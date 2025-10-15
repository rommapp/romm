<script setup lang="ts">
import { computed } from "vue";
import type { ConversionStats } from "@/__generated__";

const props = defineProps<{
  conversionStats: ConversionStats;
}>();

const conversionProgress = computed(() => {
  const stats = props.conversionStats;
  const total = stats.total || 0;
  const processed = stats.processed || 0;
  const errors = stats.errors || 0;

  return {
    processed: `${processed}/${total}`,
    processedProgress: Math.round((processed / total) * 100),
    errors: errors,
    successRate:
      total > 0 ? Math.round(((processed - errors) / total) * 100) : 0,
  };
});
</script>

<template>
  <div>
    <!-- Progress Bar -->
    <div class="mb-3">
      <div class="d-flex justify-space-between align-center mb-1">
        <span class="text-caption">Conversion Progress</span>
        <span class="text-caption"
          >{{ conversionProgress.processedProgress }}%</span
        >
      </div>
      <v-progress-linear
        :model-value="conversionProgress.processedProgress"
        color="primary"
        height="6"
        rounded
      />
    </div>

    <!-- Summary Chips -->
    <div class="d-flex flex-wrap gap-2">
      <v-chip size="x-small" color="primary" variant="outlined">
        Processed: {{ conversionProgress.processed }}
      </v-chip>
      <v-chip size="x-small" color="error" variant="outlined">
        Errors: {{ conversionProgress.errors }}
      </v-chip>
      <v-chip size="x-small" color="success" variant="outlined">
        Success Rate: {{ conversionProgress.successRate }}%
      </v-chip>
    </div>
  </div>
</template>
