<script setup lang="ts">
import { computed } from "vue";
import type { UpdateStats } from "@/__generated__";

const props = defineProps<{
  updateStats: UpdateStats;
}>();

const updateProgress = computed(() => {
  return {
    updated: `${props.updateStats.current}/${props.updateStats.total}`,
    percentage: Math.round(
      (props.updateStats.current / props.updateStats.total) * 100,
    ),
  };
});
</script>

<template>
  <div>
    <div class="mb-3">
      <div class="d-flex justify-space-between align-center mb-1">
        <span class="text-caption">Download Progress</span>
        <span class="text-caption">{{ updateProgress.percentage }}%</span>
      </div>
      <v-progress-linear
        :model-value="updateProgress.percentage"
        color="primary"
        height="6"
        rounded
      />
    </div>

    <div class="d-flex flex-wrap gap-2">
      <v-chip size="x-small" color="primary" variant="outlined">
        Downloaded: {{ updateProgress.updated }}
      </v-chip>
    </div>
  </div>
</template>
