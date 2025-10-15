<script setup lang="ts">
import { computed } from "vue";
import type {
  ScanTaskStatusResponse,
  ConversionTaskStatusResponse,
  CleanupTaskStatusResponse,
  UpdateTaskStatusResponse,
  ScanStats,
  ConversionStats,
  CleanupStats,
  UpdateStats,
} from "@/__generated__";
import CleanupTaskProgress from "./CleanupTaskProgress.vue";
import ConversionTaskProgress from "./ConversionTaskProgress.vue";
import ScanTaskProgress from "./ScanTaskProgress.vue";
import UpdateTaskProgress from "./UpdateTaskProgress.vue";

const props = defineProps<{
  task:
    | ScanTaskStatusResponse
    | ConversionTaskStatusResponse
    | CleanupTaskStatusResponse
    | UpdateTaskStatusResponse;
}>();

const scanStats = computed((): ScanStats | null => {
  if (!props.task.meta) return null;
  if (props.task.task_type !== "scan") return null;
  return props.task.meta.scan_stats;
});

const conversionStats = computed((): ConversionStats | null => {
  if (!props.task.meta) return null;
  if (props.task.task_type !== "conversion") return null;
  return props.task.meta.conversion_stats;
});

const cleanupStats = computed((): CleanupStats | null => {
  if (!props.task.meta) return null;
  if (props.task.task_type !== "cleanup") return null;
  return props.task.meta.cleanup_stats;
});

const updateStats = computed((): UpdateStats | null => {
  if (!props.task.meta) return null;
  if (props.task.task_type !== "update") return null;
  return props.task.meta.update_stats;
});

const hasDetailedStats = computed(() => {
  return !!(
    scanStats.value ||
    conversionStats.value ||
    cleanupStats.value ||
    updateStats.value
  );
});

const progressTitle = computed(() => {
  switch (props.task.task_type) {
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

// Get progress icon based on task type
const getProgressIcon = () => {
  switch (props.task.task_type) {
    case "scan":
      return "mdi-magnify-scan";
    case "conversion":
      return "mdi-image-multiple";
    case "cleanup":
      return "mdi-broom";
    case "update":
      return "mdi-update";
    default:
      return "mdi-progress-clock";
  }
};

// Get progress status color
const getProgressStatusColor = () => {
  if (props.task.status === "finished") return "success";
  if (props.task.status === "started") return "primary";
  if (props.task.status === "queued") return "warning";
  if (props.task.status === "failed") return "error";
  if (props.task.status === "stopped" || props.task.status === "canceled")
    return "grey";
  return "grey";
};

// Get progress status text
const getProgressStatusText = () => {
  if (props.task.status === "finished") return "Completed";
  if (props.task.status === "started") return "Running";
  if (props.task.status === "queued") return "Queued";
  if (props.task.status === "failed") return "Failed";
  if (props.task.status === "stopped") return "Stopped";
  if (props.task.status === "canceled") return "Canceled";
  return "Unknown";
};
</script>

<template>
  <div v-if="hasDetailedStats" class="progress-container">
    <!-- Progress Header -->
    <div class="progress-header">
      <div class="progress-title">
        <v-icon :icon="getProgressIcon()" size="18" class="mr-2" />
        {{ progressTitle }}
      </div>
      <div class="progress-status">
        <v-chip
          :color="getProgressStatusColor()"
          size="small"
          variant="flat"
          class="progress-status-chip"
        >
          {{ getProgressStatusText() }}
        </v-chip>
      </div>
    </div>

    <!-- Progress Content -->
    <div class="progress-content">
      <!-- Scan Task Progress -->
      <ScanTaskProgress
        v-if="task.task_type === 'scan' && scanStats"
        :scan-stats="scanStats"
      />

      <!-- Conversion Task Progress -->
      <ConversionTaskProgress
        v-else-if="task.task_type === 'conversion' && conversionStats"
        :conversion-stats="conversionStats"
      />

      <!-- Cleanup Task Progress -->
      <CleanupTaskProgress
        v-else-if="task.task_type === 'cleanup' && cleanupStats"
        :cleanup-stats="cleanupStats"
      />

      <!-- Update Task Progress -->
      <UpdateTaskProgress
        v-else-if="task.task_type === 'update' && updateStats"
        :update-stats="updateStats"
      />
    </div>
  </div>
</template>

<style scoped>
.progress-container {
  padding: 0 20px 20px 20px;
  background: rgba(255, 255, 255, 0.03);
  border-radius: 12px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  overflow: hidden;
  margin-top: 16px;
}

.progress-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  background: rgba(255, 255, 255, 0.05);
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.progress-title {
  display: flex;
  align-items: center;
  font-size: 16px;
  font-weight: 600;
  color: #ffffff;
}

.progress-status {
  display: flex;
  align-items: center;
}

.progress-status-chip {
  font-weight: 600;
  text-transform: capitalize;
  border-radius: 16px;
  padding: 6px 12px;
}

.progress-content {
  padding: 20px;
}

/* Responsive Design */
@media (max-width: 768px) {
  .progress-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
  }

  .progress-status {
    align-self: flex-end;
  }

  .progress-content {
    padding: 16px;
  }
}
</style>
