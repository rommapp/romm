<script setup lang="ts">
import { computed } from "vue";
import type {
  ScanStats,
  TaskProgress,
  ProgressPercentages,
} from "./task-types";

const props = defineProps<{
  scanStats: ScanStats;
  progressPercentages: ProgressPercentages | null;
}>();

const scanProgress = computed((): TaskProgress => {
  const stats = props.scanStats;
  const totalPlatforms = stats.total_platforms || 0;
  const totalRoms = stats.total_roms || 0;
  const scannedPlatforms = stats.scanned_platforms || 0;
  const scannedRoms = stats.scanned_roms || 0;

  return {
    platforms: `${scannedPlatforms}/${totalPlatforms}`,
    roms: `${scannedRoms}/${totalRoms}`,
    addedRoms: stats.added_roms || 0,
    metadataRoms: stats.metadata_roms || 0,
    scannedFirmware: stats.scanned_firmware || 0,
    addedFirmware: stats.added_firmware || 0,
  };
});
</script>

<template>
  <div>
    <!-- Progress Bars -->
    <div v-if="progressPercentages" class="mb-3">
      <div class="mb-2">
        <div class="d-flex justify-space-between align-center mb-1">
          <span class="text-caption">Platforms</span>
          <span class="text-caption">{{ progressPercentages.platforms }}%</span>
        </div>
        <v-progress-linear
          :model-value="progressPercentages.platforms"
          color="primary"
          height="6"
          rounded
        />
      </div>
      <div>
        <div class="d-flex justify-space-between align-center mb-1">
          <span class="text-caption">ROMs</span>
          <span class="text-caption">{{ progressPercentages.roms }}%</span>
        </div>
        <v-progress-linear
          :model-value="progressPercentages.roms"
          color="secondary"
          height="6"
          rounded
        />
      </div>
    </div>

    <!-- Summary Chips -->
    <div class="d-flex flex-wrap gap-2">
      <v-chip size="x-small" color="primary" variant="outlined">
        Platforms: {{ scanProgress.platforms }}
      </v-chip>
      <v-chip size="x-small" color="secondary" variant="outlined">
        ROMs: {{ scanProgress.roms }}
      </v-chip>
      <v-chip size="x-small" color="success" variant="outlined">
        Added: {{ scanProgress.addedRoms }}
      </v-chip>
      <v-chip size="x-small" color="info" variant="outlined">
        Metadata: {{ scanProgress.metadataRoms }}
      </v-chip>
      <v-chip size="x-small" color="warning" variant="outlined">
        Firmware: {{ scanProgress.scannedFirmware }}
      </v-chip>
    </div>
  </div>
</template>
