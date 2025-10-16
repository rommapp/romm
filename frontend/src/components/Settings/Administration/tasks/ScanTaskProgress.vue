<script setup lang="ts">
import { computed } from "vue";
import type { ScanStats } from "@/__generated__";

const props = defineProps<{
  scanStats: ScanStats;
}>();

const scanProgress = computed(() => {
  const stats = props.scanStats;
  const totalPlatforms = stats.total_platforms || 0;
  const totalRoms = stats.total_roms || 0;
  const scannedPlatforms = stats.scanned_platforms || 0;
  const scannedRoms = stats.scanned_roms || 0;

  return {
    platforms: `${scannedPlatforms}/${totalPlatforms}`,
    platformsPercentage: Math.round((scannedPlatforms / totalPlatforms) * 100),
    roms: `${scannedRoms}/${totalRoms}`,
    romsPercentage: Math.round((scannedRoms / totalRoms) * 100),
    addedRoms: stats.added_roms || 0,
    metadataRoms: stats.metadata_roms || 0,
    scannedFirmware: stats.scanned_firmware || 0,
    addedFirmware: stats.added_firmware || 0,
  };
});
</script>

<template>
  <div class="d-flex flex-column ga-3">
    <v-progress-linear
      :model-value="scanProgress.romsPercentage"
      color="primary"
      height="8"
      rounded
    />

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
            {{ scanProgress.addedRoms }}
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
