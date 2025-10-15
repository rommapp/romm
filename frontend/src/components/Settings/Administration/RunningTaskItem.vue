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
    case "finished":
      return "mdi-check-circle";
    case "failed":
      return "mdi-alert-circle";
    case "stopped":
    case "canceled":
      return "mdi-stop-circle";
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
    case "finished":
      return "green";
    case "failed":
      return "red";
    case "stopped":
    case "canceled":
      return "grey";
    default:
      return "grey";
  }
});

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

// Check if task has detailed stats
const hasDetailedStats = computed(() => {
  return !!(
    scanStats.value ||
    conversionStats.value ||
    cleanupStats.value ||
    downloadProgress.value
  );
});

// Get display name for task
const getTaskDisplayName = (type: TaskType) => {
  const labels = {
    scan: "Library Scan",
    conversion: "Image Conversion",
    cleanup: "Cleanup",
    update: "Metadata Update",
    watcher: "File Watcher",
    generic: "General Task",
  };
  return labels[type] || "Task";
};

// Get task type label
const getTaskTypeLabel = (type: TaskType) => {
  const labels = {
    scan: "Library Scan",
    conversion: "Image Conversion",
    cleanup: "Cleanup",
    update: "Metadata Update",
    watcher: "File Watcher",
    generic: "General Task",
  };
  return labels[type] || "Task";
};

// Calculate task duration
const getTaskDuration = () => {
  if (!props.task.started_at) return "Not started";

  const startTime = new Date(props.task.started_at);
  const endTime = props.task.ended_at
    ? new Date(props.task.ended_at)
    : new Date();
  const duration = endTime.getTime() - startTime.getTime();

  if (duration < 1000) return "< 1s";
  if (duration < 60000) return `${Math.round(duration / 1000)}s`;
  if (duration < 3600000) return `${Math.round(duration / 60000)}m`;
  return `${Math.round(duration / 3600000)}h`;
};

// Format key for display
const formatKey = (key: string) => {
  return key
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
};

// Format value for display
const formatValue = (value: any) => {
  if (typeof value === "object") {
    return JSON.stringify(value);
  }
  if (typeof value === "boolean") {
    return value ? "Yes" : "No";
  }
  return String(value);
};
</script>

<template>
  <v-card
    elevation="2"
    class="task-card"
    :class="{
      'task-card--running': task.status === 'started',
      'task-card--queued': task.status === 'queued',
      'task-card--finished': task.status === 'finished',
      'task-card--failed': task.status === 'failed',
      'task-card--stopped': task.status === 'stopped',
      'task-card--canceled': task.status === 'canceled',
    }"
  >
    <!-- Header Section -->
    <div class="task-header">
      <div class="task-header__left">
        <div class="task-icon-wrapper">
          <v-icon
            :color="statusColor"
            :icon="statusIcon"
            size="24"
            :class="{ 'task-icon--spinning': task.status === 'started' }"
          />
        </div>
        <div class="task-info">
          <h3 class="task-title">{{ getTaskDisplayName(taskType) }}</h3>
          <div class="task-meta">
            <span class="task-type">{{ getTaskTypeLabel(taskType) }}</span>
            <span class="task-separator">•</span>
            <span class="task-duration">{{ getTaskDuration() }}</span>
          </div>
        </div>
      </div>
      <div class="task-header__right">
        <v-chip
          :color="statusColor"
          size="small"
          variant="flat"
          class="task-status-chip"
        >
          <v-icon
            :icon="statusIcon"
            size="16"
            class="mr-1"
            :class="{ 'task-icon--spinning': task.status === 'started' }"
          />
          {{ task.status }}
        </v-chip>
      </div>
    </div>

    <!-- Progress Section -->
    <div v-if="hasDetailedStats" class="task-progress">
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
    </div>

    <!-- Details Section -->
    <v-expand-transition>
      <div v-if="showDetails" class="task-details">
        <!-- Task Details -->
        <div
          v-if="task.meta && Object.keys(task.meta).length > 0"
          class="task-details__section"
        >
          <h4 class="task-details__title">
            <v-icon icon="mdi-cog" size="16" class="mr-2" />
            Task Details
          </h4>
          <div class="task-details__content">
            <div class="task-details__grid">
              <div
                v-for="(value, key) in task.meta"
                :key="key"
                class="task-detail-item"
              >
                <span class="task-detail-key">{{ formatKey(key) }}</span>
                <span class="task-detail-value">
                  {{ formatValue(value) }}
                </span>
              </div>
            </div>
          </div>
        </div>

        <!-- Result Section -->
        <div v-if="task.result" class="task-details__section">
          <h4 class="task-details__title">
            <v-icon icon="mdi-check-circle" size="16" class="mr-2" />
            Result
          </h4>
          <div class="task-details__content">
            <v-card variant="outlined" class="result-card">
              <pre class="result-json">{{
                typeof task.result === "object"
                  ? JSON.stringify(task.result, null, 2)
                  : task.result
              }}</pre>
            </v-card>
          </div>
        </div>
      </div>
    </v-expand-transition>

    <div class="task-footer" v-if="hasDetailedStats">
      <v-btn
        size="small"
        variant="text"
        :icon="showDetails ? 'mdi-chevron-up' : 'mdi-chevron-down'"
        @click="toggleDetails"
        class="task-toggle-btn"
      >
        {{ showDetails ? "Hide Details" : "Show Details" }}
      </v-btn>
    </div>
  </v-card>
</template>

<style scoped>
.task-card {
  border-radius: 12px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  background: linear-gradient(
    135deg,
    rgba(255, 255, 255, 0.05) 0%,
    rgba(255, 255, 255, 0.02) 100%
  );
  transition: all 0.3s ease;
  overflow: hidden;
}

.task-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 25px rgba(0, 0, 0, 0.15);
  border-color: rgba(255, 255, 255, 0.2);
}

.task-card--running {
  border-left: 4px solid #2196f3;
  background: linear-gradient(
    135deg,
    rgba(33, 150, 243, 0.1) 0%,
    rgba(33, 150, 243, 0.05) 100%
  );
}

.task-card--queued {
  border-left: 4px solid #ff9800;
  background: linear-gradient(
    135deg,
    rgba(255, 152, 0, 0.1) 0%,
    rgba(255, 152, 0, 0.05) 100%
  );
}

.task-card--finished {
  border-left: 4px solid #4caf50;
  background: linear-gradient(
    135deg,
    rgba(76, 175, 80, 0.1) 0%,
    rgba(76, 175, 80, 0.05) 100%
  );
}

.task-card--failed {
  border-left: 4px solid #f44336;
  background: linear-gradient(
    135deg,
    rgba(244, 67, 54, 0.1) 0%,
    rgba(244, 67, 54, 0.05) 100%
  );
}

.task-card--stopped,
.task-card--canceled {
  border-left: 4px solid #9e9e9e;
  background: linear-gradient(
    135deg,
    rgba(158, 158, 158, 0.1) 0%,
    rgba(158, 158, 158, 0.05) 100%
  );
}

.task-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.task-header__left {
  display: flex;
  align-items: center;
  gap: 16px;
  flex: 1;
}

.task-icon-wrapper {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 48px;
  height: 48px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.1);
  backdrop-filter: blur(10px);
}

.task-icon--spinning {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

.task-info {
  flex: 1;
}

.task-title {
  font-size: 18px;
  font-weight: 600;
  color: #ffffff;
  margin: 0 0 4px 0;
  line-height: 1.3;
}

.task-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  color: rgba(255, 255, 255, 0.7);
}

.task-type {
  font-weight: 500;
  color: rgba(255, 255, 255, 0.9);
}

.task-separator {
  color: rgba(255, 255, 255, 0.4);
}

.task-duration {
  font-family: "Monaco", "Menlo", monospace;
  background: rgba(255, 255, 255, 0.1);
  padding: 2px 8px;
  border-radius: 6px;
  font-size: 12px;
}

.task-header__right {
  display: flex;
  align-items: center;
}

.task-status-chip {
  font-weight: 600;
  text-transform: capitalize;
  border-radius: 20px;
  padding: 8px 16px;
}

.task-progress {
  padding: 0 20px 20px 20px;
}

.task-details {
  border-top: 1px solid rgba(255, 255, 255, 0.1);
  background: rgba(0, 0, 0, 0.2);
}

.task-details__section {
  padding: 20px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}

.task-details__section:last-child {
  border-bottom: none;
}

.task-details__title {
  display: flex;
  align-items: center;
  font-size: 16px;
  font-weight: 600;
  color: #ffffff;
  margin: 0 0 16px 0;
}

.task-details__content {
  margin-top: 16px;
}

.task-details__grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 12px;
}

.task-detail-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 12px;
  background: rgba(255, 255, 255, 0.05);
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.task-detail-key {
  font-size: 12px;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.7);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.task-detail-value {
  font-size: 14px;
  color: #ffffff;
  font-family: "Monaco", "Menlo", monospace;
  word-break: break-all;
}

.result-card {
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 8px;
  overflow: hidden;
}

.result-json {
  font-family: "Monaco", "Menlo", monospace;
  font-size: 12px;
  color: #ffffff;
  margin: 0;
  padding: 16px;
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.5;
  background: transparent;
}

.task-footer {
  padding: 16px 20px;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
  display: flex;
  justify-content: center;
}

.task-toggle-btn {
  color: rgba(255, 255, 255, 0.7);
  font-weight: 500;
  text-transform: none;
}

.task-toggle-btn:hover {
  color: #ffffff;
  background: rgba(255, 255, 255, 0.1);
}

/* Responsive Design */
@media (max-width: 768px) {
  .task-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 16px;
  }

  .task-header__right {
    align-self: flex-end;
  }

  .task-details__grid {
    grid-template-columns: 1fr;
  }

  .task-meta {
    flex-direction: column;
    align-items: flex-start;
    gap: 4px;
  }

  .task-separator {
    display: none;
  }
}
</style>
