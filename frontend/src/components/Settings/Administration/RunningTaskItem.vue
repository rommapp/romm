<script setup lang="ts">
import { computed, ref } from "vue";
import type { TaskStatusResponse } from "@/__generated__";
import TaskProgressDisplay from "./tasks/TaskProgressDisplay.vue";
import type {
  ScanStats,
  ConversionStats,
  CleanupStats,
  DownloadProgress,
  TaskType,
  ProgressPercentages,
} from "./tasks/task-types";

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
const scanStats = computed((): ScanStats | null => {
  if (props.task.meta?.scan_stats) {
    return props.task.meta.scan_stats;
  }
  return null;
});

// Extract conversion stats from meta if available
const conversionStats = computed((): ConversionStats | null => {
  if (props.task.meta?.processed_count !== undefined) {
    return {
      processed: props.task.meta.processed_count || 0,
      errors: props.task.meta.error_count || 0,
      total: props.task.meta.total_files || 0,
      errorList: props.task.meta.errors || [],
    };
  }
  return null;
});

// Extract cleanup stats from result if available
const cleanupStats = computed((): CleanupStats | null => {
  if (props.task.result && typeof props.task.result === "object") {
    const result = props.task.result as any;
    if (result.removed_count !== undefined) {
      return {
        removed: result.removed_count || 0,
      };
    }
  }
  return null;
});

// Extract download progress from meta if available
const downloadProgress = computed((): DownloadProgress | null => {
  if (props.task.meta?.download_progress !== undefined) {
    return {
      progress: props.task.meta.download_progress || 0,
      total: props.task.meta.download_total || 0,
      current: props.task.meta.download_current || 0,
    };
  }
  return null;
});

// Check task type
const taskType = computed((): TaskType => {
  const taskName = props.task.task_name?.toLowerCase() || "";

  if (taskName.includes("scan") || props.task.meta?.scan_stats) {
    return "scan";
  }
  if (
    taskName.includes("convert") ||
    taskName.includes("webp") ||
    conversionStats.value
  ) {
    return "conversion";
  }
  if (
    taskName.includes("cleanup") ||
    taskName.includes("orphan") ||
    cleanupStats.value
  ) {
    return "cleanup";
  }
  if (
    taskName.includes("update") ||
    taskName.includes("metadata") ||
    taskName.includes("launchbox") ||
    taskName.includes("switch") ||
    downloadProgress.value
  ) {
    return "update";
  }
  if (taskName.includes("watcher") || taskName.includes("filesystem")) {
    return "watcher";
  }

  return "generic";
});

// Expandable details state
const showDetails = ref(false);

// Calculate progress percentages
const progressPercentages = computed((): ProgressPercentages | null => {
  if (taskType.value === "scan" && scanStats.value) {
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
  }

  if (taskType.value === "conversion" && conversionStats.value) {
    const stats = conversionStats.value;
    const total = stats.total || 0;
    const processed = stats.processed || 0;
    const progress = total > 0 ? Math.round((processed / total) * 100) : 0;

    return {
      conversion: progress,
    };
  }

  if (taskType.value === "update" && downloadProgress.value) {
    const progress = downloadProgress.value;
    const downloadProgressPercent =
      progress.total > 0
        ? Math.round((progress.current / progress.total) * 100)
        : 0;

    return {
      download: downloadProgressPercent,
    };
  }

  return null;
});

const toggleDetails = () => {
  showDetails.value = !showDetails.value;
};
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

              <!-- Task Progress Display -->
              <TaskProgressDisplay
                :task="task"
                :task-type="taskType"
                :scan-stats="scanStats"
                :conversion-stats="conversionStats"
                :cleanup-stats="cleanupStats"
                :download-progress="downloadProgress"
                :progress-percentages="progressPercentages"
                :show-details="showDetails"
                @toggle-details="toggleDetails"
              />

              <!-- Generic Meta Data Display -->
              <div
                v-if="task.meta && Object.keys(task.meta).length > 0"
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
