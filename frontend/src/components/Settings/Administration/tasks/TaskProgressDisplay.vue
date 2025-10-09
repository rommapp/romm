<script setup lang="ts">
import { computed } from "vue";
import type { TaskStatusResponse } from "@/__generated__";
import CleanupTaskProgress from "./CleanupTaskProgress.vue";
import ConversionTaskProgress from "./ConversionTaskProgress.vue";
import ScanTaskProgress from "./ScanTaskProgress.vue";
import TaskDetailedStats from "./TaskDetailedStats.vue";
import UpdateTaskProgress from "./UpdateTaskProgress.vue";
import type {
  ScanStats,
  ConversionStats,
  CleanupStats,
  DownloadProgress,
  TaskType,
  ProgressPercentages,
} from "./task-types";

const props = defineProps<{
  task: TaskStatusResponse;
  taskType: TaskType;
  scanStats?: ScanStats | null;
  conversionStats?: ConversionStats | null;
  cleanupStats?: CleanupStats | null;
  downloadProgress?: DownloadProgress | null;
  progressPercentages: ProgressPercentages | null;
  showDetails: boolean;
}>();

const emit = defineEmits<{
  "toggle-details": [];
}>();

const hasDetailedStats = computed(() => {
  return !!(
    props.scanStats ||
    props.conversionStats ||
    props.cleanupStats ||
    props.downloadProgress
  );
});

const progressTitle = computed(() => {
  switch (props.taskType) {
    case "scan":
      return "Scan Progress";
    case "conversion":
      return "Conversion Progress";
    case "cleanup":
      return "Cleanup Progress";
    case "update":
      return "Update Progress";
    default:
      return "Task Progress";
  }
});
</script>

<template>
  <div v-if="taskType !== 'generic' && hasDetailedStats" class="mt-2">
    <v-divider class="mb-2" />
    <div class="d-flex align-center justify-space-between mb-1">
      <div class="text-caption text-blue-grey-lighten-1">
        {{ progressTitle }}
      </div>
      <v-btn
        v-if="hasDetailedStats"
        size="x-small"
        variant="text"
        :icon="showDetails ? 'mdi-chevron-up' : 'mdi-chevron-down'"
        @click="emit('toggle-details')"
      />
    </div>

    <!-- Scan Task Progress -->
    <ScanTaskProgress
      v-if="taskType === 'scan' && scanStats"
      :scan-stats="scanStats"
      :progress-percentages="progressPercentages"
    />

    <!-- Conversion Task Progress -->
    <ConversionTaskProgress
      v-else-if="taskType === 'conversion' && conversionStats"
      :conversion-stats="conversionStats"
      :progress-percentages="progressPercentages"
    />

    <!-- Cleanup Task Progress -->
    <CleanupTaskProgress
      v-else-if="taskType === 'cleanup' && cleanupStats"
      :cleanup-stats="cleanupStats"
    />

    <!-- Update Task Progress -->
    <UpdateTaskProgress
      v-else-if="taskType === 'update' && downloadProgress"
      :download-progress="downloadProgress"
      :progress-percentages="progressPercentages"
    />

    <!-- Detailed Stats (Expandable) -->
    <v-expand-transition>
      <div v-if="showDetails && hasDetailedStats" class="mt-3">
        <TaskDetailedStats
          :task-type="taskType"
          :scan-stats="scanStats"
          :conversion-stats="conversionStats"
          :cleanup-stats="cleanupStats"
          :download-progress="downloadProgress"
        />
      </div>
    </v-expand-transition>
  </div>
</template>
