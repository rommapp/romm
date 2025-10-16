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
  <div class="d-flex flex-column ga-4">
    <div class="d-flex flex-column">
      <div
        class="d-flex align-center justify-space-between gap-4 font-weight-semibold text-white"
      >
        <v-progress-linear
          :model-value="scanProgress.romsPercentage"
          color="primary"
          height="12"
          rounded
        />
        <v-chip size="small" variant="tonal">
          {{ scanProgress.romsPercentage }}%
        </v-chip>
      </div>
      <div class="text-grey-lighten-1">
        {{ scanProgress.roms }} ROMs and {{ scanProgress.platforms }} platforms
        processed
      </div>
    </div>

    <div class="grid grid-cols-5 gap-4">
      <v-card
        variant="tonal"
        class="d-flex align-center ga-3 pa-4 border-l-4 border-primary"
      >
        <v-avatar size="40" class="bg-primary-lighten-1">
          <v-icon icon="mdi-console" size="20" />
        </v-avatar>
        <div class="d-flex flex-column ga-1 flex-grow-1">
          <div class="text-h6 font-weight-bold text-white">
            {{ scanProgress.platforms }}
          </div>
          <div class="text-grey-lighten-1 font-weight-medium text-uppercase">
            Platforms
          </div>
        </div>
      </v-card>

      <v-card
        variant="tonal"
        class="d-flex align-center ga-3 pa-4 border-l-4 border-secondary"
      >
        <v-avatar size="40" class="bg-secondary-lighten-1">
          <v-icon icon="mdi-gamepad-variant" size="20" />
        </v-avatar>
        <div class="d-flex flex-column ga-1 flex-grow-1">
          <div class="text-h6 font-weight-bold text-white">
            {{ scanProgress.roms }}
          </div>
          <div class="text-grey-lighten-1 font-weight-medium text-uppercase">
            ROMs
          </div>
        </div>
      </v-card>

      <v-card
        variant="tonal"
        class="d-flex align-center ga-3 pa-4 border-l-4 border-success"
      >
        <v-avatar size="40" class="bg-success-lighten-1">
          <v-icon icon="mdi-plus-circle" size="20" />
        </v-avatar>
        <div class="d-flex flex-column ga-1 flex-grow-1">
          <div class="text-h6 font-weight-bold text-white">
            {{ scanProgress.addedRoms }}
          </div>
          <div class="text-grey-lighten-1 font-weight-medium text-uppercase">
            Added
          </div>
        </div>
      </v-card>

      <v-card
        variant="tonal"
        class="d-flex align-center ga-3 pa-4 border-l-4 border-info"
      >
        <v-avatar size="40" class="bg-info-lighten-1">
          <v-icon icon="mdi-information" size="20" />
        </v-avatar>
        <div class="d-flex flex-column ga-1 flex-grow-1">
          <div class="text-h6 font-weight-bold text-white">
            {{ scanProgress.metadataRoms }}
          </div>
          <div class="text-grey-lighten-1 font-weight-medium text-uppercase">
            Metadata
          </div>
        </div>
      </v-card>

      <v-card
        variant="tonal"
        class="d-flex align-center ga-3 pa-4 border-l-4 border-warning"
      >
        <v-avatar size="40" class="bg-warning-lighten-1">
          <v-icon icon="mdi-chip" size="20" />
        </v-avatar>
        <div class="d-flex flex-column ga-1 flex-grow-1">
          <div class="text-h6 font-weight-bold text-white">
            {{ scanProgress.scannedFirmware }}
          </div>
          <div class="text-grey-lighten-1 font-weight-medium text-uppercase">
            Firmware
          </div>
        </div>
      </v-card>
    </div>
  </div>
</template>
