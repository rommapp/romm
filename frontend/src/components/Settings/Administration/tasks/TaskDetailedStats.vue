<script setup lang="ts">
import type {
  ScanStats,
  ConversionStats,
  CleanupStats,
  DownloadProgress,
  TaskType,
} from "./task-types";

const props = defineProps<{
  taskType: TaskType;
  scanStats?: ScanStats | null;
  conversionStats?: ConversionStats | null;
  cleanupStats?: CleanupStats | null;
  downloadProgress?: DownloadProgress | null;
}>();
</script>

<template>
  <v-card variant="outlined" class="pa-3">
    <div class="text-caption text-blue-grey-lighten-1 mb-2">
      Detailed Statistics
    </div>

    <!-- Scan Stats Details -->
    <v-row v-if="taskType === 'scan' && scanStats" dense>
      <v-col cols="6" sm="4">
        <div class="text-caption">Total Platforms</div>
        <div class="text-h6">{{ scanStats.total_platforms || 0 }}</div>
      </v-col>
      <v-col cols="6" sm="4">
        <div class="text-caption">Scanned Platforms</div>
        <div class="text-h6">{{ scanStats.scanned_platforms || 0 }}</div>
      </v-col>
      <v-col cols="6" sm="4">
        <div class="text-caption">New Platforms</div>
        <div class="text-h6">{{ scanStats.new_platforms || 0 }}</div>
      </v-col>
      <v-col cols="6" sm="4">
        <div class="text-caption">Identified Platforms</div>
        <div class="text-h6">{{ scanStats.identified_platforms || 0 }}</div>
      </v-col>
      <v-col cols="6" sm="4">
        <div class="text-caption">Total ROMs</div>
        <div class="text-h6">{{ scanStats.total_roms || 0 }}</div>
      </v-col>
      <v-col cols="6" sm="4">
        <div class="text-caption">Scanned ROMs</div>
        <div class="text-h6">{{ scanStats.scanned_roms || 0 }}</div>
      </v-col>
      <v-col cols="6" sm="4">
        <div class="text-caption">Added ROMs</div>
        <div class="text-h6">{{ scanStats.added_roms || 0 }}</div>
      </v-col>
      <v-col cols="6" sm="4">
        <div class="text-caption">Metadata ROMs</div>
        <div class="text-h6">{{ scanStats.metadata_roms || 0 }}</div>
      </v-col>
      <v-col cols="6" sm="4">
        <div class="text-caption">Scanned Firmware</div>
        <div class="text-h6">{{ scanStats.scanned_firmware || 0 }}</div>
      </v-col>
      <v-col cols="6" sm="4">
        <div class="text-caption">Added Firmware</div>
        <div class="text-h6">{{ scanStats.added_firmware || 0 }}</div>
      </v-col>
    </v-row>

    <!-- Conversion Stats Details -->
    <v-row v-else-if="taskType === 'conversion' && conversionStats" dense>
      <v-col cols="6" sm="4">
        <div class="text-caption">Total Files</div>
        <div class="text-h6">{{ conversionStats.total }}</div>
      </v-col>
      <v-col cols="6" sm="4">
        <div class="text-caption">Processed</div>
        <div class="text-h6">{{ conversionStats.processed }}</div>
      </v-col>
      <v-col cols="6" sm="4">
        <div class="text-caption">Errors</div>
        <div class="text-h6">{{ conversionStats.errors }}</div>
      </v-col>
      <v-col
        cols="12"
        v-if="conversionStats.errorList && conversionStats.errorList.length > 0"
      >
        <div class="text-caption">Error Details</div>
        <div class="text-caption text-red">
          {{ conversionStats.errorList.slice(0, 5).join(", ") }}
          <span v-if="conversionStats.errorList.length > 5">...</span>
        </div>
      </v-col>
    </v-row>

    <!-- Cleanup Stats Details -->
    <v-row v-else-if="taskType === 'cleanup' && cleanupStats" dense>
      <v-col cols="6" sm="4">
        <div class="text-caption">Removed Items</div>
        <div class="text-h6">{{ cleanupStats.removed }}</div>
      </v-col>
    </v-row>

    <!-- Download Stats Details -->
    <v-row v-else-if="taskType === 'update' && downloadProgress" dense>
      <v-col cols="6" sm="4">
        <div class="text-caption">Downloaded</div>
        <div class="text-h6">
          {{ downloadProgress.current }}/{{ downloadProgress.total }}
        </div>
      </v-col>
      <v-col cols="6" sm="4">
        <div class="text-caption">Progress</div>
        <div class="text-h6">{{ downloadProgress.progress }}%</div>
      </v-col>
    </v-row>
  </v-card>
</template>
