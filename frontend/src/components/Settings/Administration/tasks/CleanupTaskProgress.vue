<script setup lang="ts">
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import type { CleanupStats, CleanupTaskStatusResponse } from "@/__generated__";

const { t } = useI18n();

const props = defineProps<{
  task: CleanupTaskStatusResponse;
  cleanupStats: CleanupStats;
}>();

const cleanupProgress = computed(() => {
  const {
    platforms_in_db,
    roms_in_db,
    platforms_in_fs,
    roms_in_fs,
    removed_fs_platforms,
    removed_fs_roms,
  } = props.cleanupStats;

  const platformsToRemove = Math.max(platforms_in_fs - platforms_in_db, 0);
  const romsToRemove = Math.max(roms_in_fs - roms_in_db, 0);

  const itemsToRemove = platformsToRemove + romsToRemove;
  const removedItems = removed_fs_platforms + removed_fs_roms;

  return {
    removedFsPlatforms: removed_fs_platforms,
    removedFsRoms: removed_fs_roms,
    platformsToRemove: platformsToRemove,
    romsToRemove: romsToRemove,
    platformsInDB: platforms_in_db,
    romsInDB: roms_in_db,
    percentage:
      itemsToRemove > 0
        ? Math.round((removedItems / itemsToRemove) * 100)
        : 100,
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

    <div class="grid grid-cols-3 gap-4">
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
            {{ cleanupProgress.removedFsPlatforms }}/{{
              cleanupProgress.platformsToRemove
            }}/{{ cleanupProgress.platformsInDB }}
          </div>
          <div class="text-uppercase">{{ t("common.platforms") }}</div>
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
            {{ cleanupProgress.removedFsRoms }}/{{
              cleanupProgress.romsToRemove
            }}/{{ cleanupProgress.romsInDB }}
          </div>
          <div class="text-uppercase">ROMs</div>
        </div>
      </v-card>

      <v-card
        variant="tonal"
        class="d-flex align-center ga-3 px-2 py-1 border-l-4 border-warning stat-card--success"
      >
        <div
          class="d-flex flex-row align-center justify-center ga-1 flex-grow-1"
        >
          <v-avatar size="24" class="bg-warning-lighten-1">
            <v-icon icon="mdi-percent" size="20" />
          </v-avatar>
          <div class="font-weight-bold">{{ cleanupProgress.percentage }}%</div>
          <div class="text-uppercase">{{ t("settings.progress") }}</div>
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
