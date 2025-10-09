<script setup lang="ts">
import { computed } from "vue";
import type {
  DownloadProgress,
  TaskProgress,
  ProgressPercentages,
} from "./task-types";

const props = defineProps<{
  downloadProgress: DownloadProgress;
  progressPercentages: ProgressPercentages | null;
}>();

const updateProgress = computed((): TaskProgress => {
  const progress = props.downloadProgress;
  return {
    downloaded: `${progress.current}/${progress.total}`,
  };
});
</script>

<template>
  <div>
    <!-- Progress Bar -->
    <div v-if="progressPercentages" class="mb-3">
      <div class="d-flex justify-space-between align-center mb-1">
        <span class="text-caption">Download Progress</span>
        <span class="text-caption">{{ progressPercentages.download }}%</span>
      </div>
      <v-progress-linear
        :model-value="progressPercentages.download"
        color="primary"
        height="6"
        rounded
      />
    </div>

    <!-- Summary Chips -->
    <div class="d-flex flex-wrap gap-2">
      <v-chip size="x-small" color="primary" variant="outlined">
        Downloaded: {{ updateProgress.downloaded }}
      </v-chip>
    </div>
  </div>
</template>
