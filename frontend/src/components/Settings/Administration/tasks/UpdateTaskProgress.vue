<script setup lang="ts">
import { computed } from "vue";
import type { UpdateStats, UpdateTaskStatusResponse } from "@/__generated__";

const props = defineProps<{
  task: UpdateTaskStatusResponse;
  updateStats: UpdateStats;
}>();

const updateProgress = computed(() => {
  const { processed, total } = props.updateStats;
  return total > 0 ? Math.round((processed / total) * 100) : 100;
});
</script>

<template>
  <div class="d-flex flex-column ga-3">
    <div
      v-if="['started', 'stopped'].includes(task.status)"
      class="overflow-hidden w-100 h-100 position-absolute top-0 left-0"
    >
      <div
        class="progress-bar-fill h-100 rounded"
        :style="{ width: `${updateProgress}%` }"
      />
    </div>
  </div>
</template>

<style scoped>
.progress-bar-fill {
  background: linear-gradient(
    90deg,
    rgba(var(--v-theme-primary), 0.35) 0%,
    rgba(var(--v-theme-primary), 0.2) 50%,
    rgba(var(--v-theme-primary), 0.35) 100%
  );
  animation: progress-pulse 2s ease-in-out infinite;
  transition: width 0.3s ease;
}

@keyframes progress-pulse {
  0% {
    opacity: 0.8;
  }
  50% {
    opacity: 1;
  }
  100% {
    opacity: 0.8;
  }
}
</style>
