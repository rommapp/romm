<script setup lang="ts">
import { computed } from "vue";
import type { ScanStats, ScanTaskStatusResponse } from "@/__generated__";

const props = defineProps<{
  task: ScanTaskStatusResponse;
  scanStats: ScanStats;
}>();

const scanProgress = computed(() => {
  const {
    total_platforms,
    total_roms,
    scanned_platforms,
    scanned_roms,
    new_roms,
    identified_roms,
    scanned_firmware,
    new_firmware,
  } = props.scanStats;

  return {
    platforms: `${scanned_platforms}/${total_platforms}`,
    platformsPercentage: Math.round(
      (scanned_platforms / total_platforms) * 100,
    ),
    roms: `${scanned_roms}/${total_roms}`,
    romsPercentage: Math.round((scanned_roms / total_roms) * 100),
    newRoms: new_roms,
    metadataRoms: identified_roms,
    scannedFirmware: scanned_firmware,
    newFirmware: new_firmware,
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
        :style="{ width: `${scanProgress.platformsPercentage}%` }"
      />
    </div>

    <div class="grid grid-cols-5 gap-4">
      <v-card
        variant="tonal"
        class="d-flex align-center ga-3 px-2 py-1 border-l-4 border-primary stat-card--primary"
      >
        <div
          class="d-flex flex-row align-center justify-center ga-1 flex-grow-1"
        >
          <v-avatar size="24" class="bg-primary-lighten-1">
            <v-icon icon="mdi-console" size="20" />
          </v-avatar>
          <div class="font-weight-bold">
            {{ scanProgress.platforms }}
          </div>
          <div class="text-uppercase">Platforms</div>
        </div>
      </v-card>

      <v-card
        variant="tonal"
        class="d-flex align-center ga-3 px-2 py-1 border-l-4 border-secondary stat-card--secondary"
      >
        <div
          class="d-flex flex-row align-center justify-center ga-1 flex-grow-1"
        >
          <v-avatar size="24" class="bg-secondary-lighten-1">
            <v-icon icon="mdi-gamepad-variant" size="20" />
          </v-avatar>
          <div class="font-weight-bold">
            {{ scanProgress.roms }}
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
            <v-icon icon="mdi-plus-circle" size="20" />
          </v-avatar>
          <div class="font-weight-bold">
            {{ scanProgress.newRoms }}
          </div>
          <div class="text-uppercase">Added</div>
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
            <v-icon icon="mdi-information" size="20" />
          </v-avatar>
          <div class="font-weight-bold">
            {{ scanProgress.metadataRoms }}
          </div>
          <div class="text-uppercase">Metadata</div>
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
            <v-icon icon="mdi-chip" size="20" />
          </v-avatar>
          <div class="font-weight-bold">
            {{ scanProgress.scannedFirmware }}
          </div>
          <div class="text-uppercase">Firmware</div>
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

.stat-card--secondary {
  background: rgba(var(--v-theme-accent), 0.1);
}

.stat-card--success {
  background: rgba(var(--v-theme-success), 0.1);
}

.stat-card--info {
  background: rgba(var(--v-theme-info), 0.1);
}

.stat-card--warning {
  background: rgba(var(--v-theme-error), 0.1);
}
</style>
