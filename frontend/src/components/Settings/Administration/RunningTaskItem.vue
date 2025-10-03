<script setup lang="ts">
import { computed, ref } from "vue";
import type { TaskStatusResponse } from "@/__generated__";

const props = defineProps<{
  task: TaskStatusResponse;
}>();

const statusIcon = computed(() => {
  switch (props.task.status) {
    case "queued":
      return "mdi-clock-outline";
    case "started":
      return "mdi-loading";
    default:
      return "mdi-help-circle-outline";
  }
});

const statusColor = computed(() => {
  switch (props.task.status) {
    case "queued":
      return "orange";
    case "started":
      return "blue";
    default:
      return "grey";
  }
});

const formatDateTime = (dateTime: string | null) => {
  if (!dateTime) return "N/A";
  return new Date(dateTime).toLocaleString();
};

// Extract scan stats from meta if available
const scanStats = computed(() => {
  if (props.task.meta?.scan_stats) {
    return props.task.meta.scan_stats;
  }
  return null;
});

// Format scan progress for display
const scanProgress = computed(() => {
  if (!scanStats.value) return null;

  const stats = scanStats.value;
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

// Check if this is a scan task
const isScanTask = computed(() => {
  return (
    props.task.task_name?.toLowerCase().includes("scan") ||
    props.task.meta?.scan_stats
  );
});

// Expandable details state
const showDetails = ref(false);

// Calculate progress percentages
const progressPercentages = computed(() => {
  if (!scanStats.value) return null;

  const stats = scanStats.value;
  const platformProgress =
    stats.total_platforms > 0
      ? Math.round((stats.scanned_platforms / stats.total_platforms) * 100)
      : 0;
  const romProgress =
    stats.total_roms > 0
      ? Math.round((stats.scanned_roms / stats.total_roms) * 100)
      : 0;

  return {
    platforms: platformProgress,
    roms: romProgress,
  };
});
</script>

<template>
  <v-card elevation="0" class="bg-background">
    <v-row no-gutters>
      <v-col>
        <v-list-item class="pa-0">
          <template #prepend>
            <v-icon :color="statusColor" :icon="statusIcon" />
          </template>
          <v-list-item-title class="font-weight-bold">
            {{ task.task_name }}
          </v-list-item-title>
          <v-list-item-subtitle>
            <div class="d-flex flex-column">
              <span>Status: {{ task.status }}</span>
              <span v-if="task.queued_at">
                Queued: {{ formatDateTime(task.queued_at) }}
              </span>
              <span v-if="task.started_at">
                Started: {{ formatDateTime(task.started_at) }}
              </span>

              <!-- Scan Progress Display -->
              <div v-if="isScanTask && scanProgress" class="mt-2">
                <v-divider class="mb-2" />
                <div class="d-flex align-center justify-space-between mb-1">
                  <div class="text-caption text-blue-grey-lighten-1">
                    Scan Progress
                  </div>
                  <v-btn
                    v-if="scanStats"
                    size="x-small"
                    variant="text"
                    :icon="showDetails ? 'mdi-chevron-up' : 'mdi-chevron-down'"
                    @click="showDetails = !showDetails"
                  />
                </div>
                <!-- Progress Bars -->
                <div v-if="progressPercentages" class="mb-3">
                  <div class="mb-2">
                    <div class="d-flex justify-space-between align-center mb-1">
                      <span class="text-caption">Platforms</span>
                      <span class="text-caption"
                        >{{ progressPercentages.platforms }}%</span
                      >
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
                      <span class="text-caption"
                        >{{ progressPercentages.roms }}%</span
                      >
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

                <!-- Detailed Scan Stats -->
                <v-expand-transition>
                  <div v-if="showDetails && scanStats" class="mt-3">
                    <v-card variant="outlined" class="pa-3">
                      <div class="text-caption text-blue-grey-lighten-1 mb-2">
                        Detailed Statistics
                      </div>
                      <v-row dense>
                        <v-col cols="6" sm="4">
                          <div class="text-caption">Total Platforms</div>
                          <div class="text-h6">
                            {{ scanStats.total_platforms || 0 }}
                          </div>
                        </v-col>
                        <v-col cols="6" sm="4">
                          <div class="text-caption">Scanned Platforms</div>
                          <div class="text-h6">
                            {{ scanStats.scanned_platforms || 0 }}
                          </div>
                        </v-col>
                        <v-col cols="6" sm="4">
                          <div class="text-caption">New Platforms</div>
                          <div class="text-h6">
                            {{ scanStats.new_platforms || 0 }}
                          </div>
                        </v-col>
                        <v-col cols="6" sm="4">
                          <div class="text-caption">Identified Platforms</div>
                          <div class="text-h6">
                            {{ scanStats.identified_platforms || 0 }}
                          </div>
                        </v-col>
                        <v-col cols="6" sm="4">
                          <div class="text-caption">Total ROMs</div>
                          <div class="text-h6">
                            {{ scanStats.total_roms || 0 }}
                          </div>
                        </v-col>
                        <v-col cols="6" sm="4">
                          <div class="text-caption">Scanned ROMs</div>
                          <div class="text-h6">
                            {{ scanStats.scanned_roms || 0 }}
                          </div>
                        </v-col>
                        <v-col cols="6" sm="4">
                          <div class="text-caption">Added ROMs</div>
                          <div class="text-h6">
                            {{ scanStats.added_roms || 0 }}
                          </div>
                        </v-col>
                        <v-col cols="6" sm="4">
                          <div class="text-caption">Metadata ROMs</div>
                          <div class="text-h6">
                            {{ scanStats.metadata_roms || 0 }}
                          </div>
                        </v-col>
                        <v-col cols="6" sm="4">
                          <div class="text-caption">Scanned Firmware</div>
                          <div class="text-h6">
                            {{ scanStats.scanned_firmware || 0 }}
                          </div>
                        </v-col>
                        <v-col cols="6" sm="4">
                          <div class="text-caption">Added Firmware</div>
                          <div class="text-h6">
                            {{ scanStats.added_firmware || 0 }}
                          </div>
                        </v-col>
                      </v-row>
                    </v-card>
                  </div>
                </v-expand-transition>
              </div>

              <!-- Generic Meta Data Display -->
              <div
                v-else-if="task.meta && Object.keys(task.meta).length > 0"
                class="mt-2"
              >
                <v-divider class="mb-2" />
                <div class="text-caption text-blue-grey-lighten-1 mb-1">
                  Task Details
                </div>
                <div class="d-flex flex-wrap gap-1">
                  <v-chip
                    v-for="(value, key) in task.meta"
                    :key="key"
                    size="x-small"
                    color="grey"
                    variant="outlined"
                  >
                    {{ key }}:
                    {{
                      typeof value === "object" ? JSON.stringify(value) : value
                    }}
                  </v-chip>
                </div>
              </div>

              <!-- Result Display -->
              <div v-if="task.result" class="mt-2">
                <v-divider class="mb-2" />
                <div class="text-caption text-blue-grey-lighten-1 mb-1">
                  Result
                </div>
                <v-card variant="outlined" class="pa-2">
                  <pre
                    class="text-caption"
                    style="white-space: pre-wrap; word-break: break-word"
                    >{{
                      typeof task.result === "object"
                        ? JSON.stringify(task.result, null, 2)
                        : task.result
                    }}</pre
                  >
                </v-card>
              </div>
            </div>
          </v-list-item-subtitle>
        </v-list-item>
      </v-col>
      <v-col cols="auto" class="d-flex align-center">
        <v-chip :color="statusColor" size="small" variant="outlined">
          {{ task.status }}
        </v-chip>
      </v-col>
    </v-row>
  </v-card>
</template>
