<script setup lang="ts">
import { computed } from "vue";
import type {
  ConversionStats,
  ConversionTaskStatusResponse,
} from "@/__generated__";

const props = defineProps<{
  task: ConversionTaskStatusResponse;
  conversionStats: ConversionStats;
}>();

const conversionProgress = computed(() => {
  const { processed, total, errors } = props.conversionStats;

  return {
    processed: `${processed}/${total}`,
    percentage: Math.round((processed / total) * 100),
    errors: errors,
    successRate:
      total > 0 ? Math.round(((processed - errors) / total) * 100) : 100,
  };
});
</script>

<template>
  <div class="d-flex flex-column ga-3 pt-2">
    <div
      v-if="['started', 'stopped'].includes(task.status)"
      class="overflow-hidden w-100 h-100 position-absolute top-0 left-0"
    >
      <div
        class="progress-bar-fill h-100 rounded"
        :style="{ width: `${conversionProgress.percentage}%` }"
      />
    </div>

    <div class="grid grid-cols-3 gap-4">
      <v-card
        variant="tonal"
        class="d-flex align-center ga-3 px-2 py-1 border-l-4 border-primary stat-card--primary"
      >
        <div
          class="d-flex flex-row align-center justify-center ga-1 flex-grow-1"
        >
          <v-avatar size="24" class="bg-primary-lighten-1">
            <v-icon icon="mdi-check-circle" size="20" />
          </v-avatar>
          <div class="font-weight-bold">
            {{ conversionProgress.processed }}
          </div>
          <div class="text-uppercase">Processed</div>
        </div>
      </v-card>

      <v-card
        variant="tonal"
        class="d-flex align-center ga-3 px-2 py-1 border-l-4 border-error stat-card--error"
      >
        <div
          class="d-flex flex-row align-center justify-center ga-1 flex-grow-1"
        >
          <v-avatar size="24" class="bg-error-lighten-1">
            <v-icon icon="mdi-alert-circle" size="20" />
          </v-avatar>
          <div class="font-weight-bold">
            {{ conversionProgress.errors }}
          </div>
          <div class="text-uppercase">Errors</div>
        </div>
      </v-card>

      <v-card
        variant="tonal"
        class="d-flex align-center ga-3 px-2 py-1 border-l-4 border-success stat-card--success"
      >
        <div
          class="d-flex flex-row align-center justify-center ga-1 flex-grow-1"
        >
          <v-avatar size="24" class="bg-success-lighten-1">
            <v-icon icon="mdi-percent" size="20" />
          </v-avatar>
          <div class="font-weight-bold">
            {{ conversionProgress.successRate }}%
          </div>
          <div class="text-uppercase">Success</div>
        </div>
      </v-card>
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

.stat-card--primary {
  background: rgba(var(--v-theme-primary), 0.1);
}

.stat-card--error {
  background: rgba(var(--v-theme-error), 0.1);
}

.stat-card--success {
  background: rgba(var(--v-theme-success), 0.1);
}
</style>
