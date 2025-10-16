<script setup lang="ts">
import { computed } from "vue";
import type { CleanupStats, CleanupTaskStatusResponse } from "@/__generated__";

const props = defineProps<{
  task: CleanupTaskStatusResponse;
  cleanupStats: CleanupStats;
}>();

const cleanupProgress = computed(() => {
  const { total_platforms, total_roms, removed_platforms, removed_roms } =
    props.cleanupStats;
  const totalPlatforms = total_platforms || 0;
  const totalRoms = total_roms || 0;
  const totalItems = totalPlatforms + totalRoms;
  const removedPlatforms = removed_platforms || 0;
  const removedRoms = removed_roms || 0;
  const removedItems = removedPlatforms + removedRoms;

  return {
    totalPlatforms: totalPlatforms,
    totalRoms: totalRoms,
    removedPlatforms: removedPlatforms,
    removedRoms: removedRoms,
    totalItems: totalItems,
    removedItems: removedItems,
    percentage:
      totalItems > 0 ? Math.round((removedItems / totalItems) * 100) : 100,
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
        :style="{ width: `${cleanupProgress.percentage}%` }"
      />
    </div>

    <div class="grid grid-cols-4 gap-4">
      <v-card
        variant="tonal"
        class="d-flex align-center ga-3 px-2 py-1 border-l-4 border-primary stat-card--primary"
      >
        <div
          class="d-flex flex-row align-center justify-center ga-1 flex-grow-1"
        >
          <v-avatar size="24" class="bg-primary-lighten-1">
            <v-icon icon="mdi-folder" size="20" />
          </v-avatar>
          <div class="font-weight-bold">
            {{ cleanupProgress.removedPlatforms }}/{{
              cleanupProgress.totalPlatforms
            }}
          </div>
          <div class="text-uppercase">Platforms</div>
        </div>
      </v-card>

      <v-card
        variant="tonal"
        class="d-flex align-center ga-3 px-2 py-1 border-l-4 border-info stat-card--info"
      >
        <div
          class="d-flex flex-row align-center justify-center ga-1 flex-grow-1"
        >
          <v-avatar size="24" class="bg-info-lighten-1">
            <v-icon icon="mdi-gamepad-variant" size="20" />
          </v-avatar>
          <div class="font-weight-bold">
            {{ cleanupProgress.removedRoms }}/{{ cleanupProgress.totalRoms }}
          </div>
          <div class="text-uppercase">ROMs</div>
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
            <v-icon icon="mdi-delete" size="20" />
          </v-avatar>
          <div class="font-weight-bold">
            {{ cleanupProgress.removedItems }}
          </div>
          <div class="text-uppercase">Removed</div>
        </div>
      </v-card>

      <v-card
        variant="tonal"
        class="d-flex align-center ga-3 px-2 py-1 border-l-4 border-warning stat-card--warning"
      >
        <div
          class="d-flex flex-row align-center justify-center ga-1 flex-grow-1"
        >
          <v-avatar size="24" class="bg-warning-lighten-1">
            <v-icon icon="mdi-percent" size="20" />
          </v-avatar>
          <div class="font-weight-bold">{{ cleanupProgress.percentage }}%</div>
          <div class="text-uppercase">Progress</div>
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

.stat-card--info {
  background: rgba(var(--v-theme-info), 0.1);
}

.stat-card--success {
  background: rgba(var(--v-theme-success), 0.1);
}

.stat-card--warning {
  background: rgba(var(--v-theme-warning), 0.1);
}
</style>
