<script setup lang="ts">
import { storeToRefs } from "pinia";
import { computed, nextTick, onMounted, onUnmounted, ref } from "vue";
import RunningTaskItem from "@/components/Settings/Administration/RunningTaskItem.vue";
import TaskOption from "@/components/Settings/Administration/TaskOption.vue";
import RSection from "@/components/common/RSection.vue";
import storeTasks from "@/stores/tasks";
import { convertCronExperssion } from "@/utils";

const tasksStore = storeTasks();
const { watcherTasks, scheduledTasks, manualTasks, taskStatuses } =
  storeToRefs(tasksStore);

const watcherTasksUI = computed(() =>
  watcherTasks.value.map((task) => ({
    ...task,
    icon: task.enabled ? "mdi-file-check-outline" : "mdi-file-remove-outline",
  })),
);

const scheduledTasksUI = computed(() =>
  scheduledTasks.value.map((task) => ({
    ...task,
    icon: task.enabled ? "mdi-clock-check-outline" : "mdi-clock-remove-outline",
    cron_string: convertCronExperssion(task.cron_string),
  })),
);

const manualTasksUI = computed(() =>
  manualTasks.value.map((task) => ({
    ...task,
    icon: getManualTaskIcon(task.name),
  })),
);

// Get active scan tasks with progress
const activeScanTasks = computed(() => {
  return taskStatuses.value.filter(
    (task) =>
      task.status === "started" &&
      (task.task_name?.toLowerCase().includes("scan") || task.meta?.scan_stats),
  );
});

// Calculate overall scan progress
const overallScanProgress = computed(() => {
  if (activeScanTasks.value.length === 0) return null;

  const totalStats = activeScanTasks.value.reduce(
    (acc, task) => {
      if (task.meta?.scan_stats) {
        const stats = task.meta.scan_stats;
        acc.totalPlatforms += stats.total_platforms || 0;
        acc.scannedPlatforms += stats.scanned_platforms || 0;
        acc.totalRoms += stats.total_roms || 0;
        acc.scannedRoms += stats.scanned_roms || 0;
        acc.addedRoms += stats.added_roms || 0;
        acc.metadataRoms += stats.metadata_roms || 0;
      }
      return acc;
    },
    {
      totalPlatforms: 0,
      scannedPlatforms: 0,
      totalRoms: 0,
      scannedRoms: 0,
      addedRoms: 0,
      metadataRoms: 0,
    },
  );

  const platformProgress =
    totalStats.totalPlatforms > 0
      ? Math.round(
          (totalStats.scannedPlatforms / totalStats.totalPlatforms) * 100,
        )
      : 0;
  const romProgress =
    totalStats.totalRoms > 0
      ? Math.round((totalStats.scannedRoms / totalStats.totalRoms) * 100)
      : 0;

  return {
    platformProgress,
    romProgress,
    totalPlatforms: totalStats.totalPlatforms,
    scannedPlatforms: totalStats.scannedPlatforms,
    totalRoms: totalStats.totalRoms,
    scannedRoms: totalStats.scannedRoms,
    addedRoms: totalStats.addedRoms,
    metadataRoms: totalStats.metadataRoms,
  };
});

// Icon mapping for manual tasks
const getManualTaskIcon = (taskName: string) => {
  const iconMap: Record<string, string> = {
    cleanup_orphaned_resources: "mdi-broom",
  };
  return iconMap[taskName] || "mdi-play";
};

// Fetch task status
const fetchTaskStatus = async () => {
  try {
    await tasksStore.fetchTaskStatus();
    // Use nextTick to ensure DOM updates are complete before next operation
    await nextTick();
  } catch (error) {
    console.error("Error fetching task status:", error);
  }
};

// Auto-refresh task status every 5 seconds
let refreshInterval: NodeJS.Timeout | null = null;

onMounted(() => {
  fetchTaskStatus();
  refreshInterval = setInterval(() => {
    // Add error handling to prevent uncaught promise rejections
    fetchTaskStatus().catch((error) => {
      console.error("Error in task status refresh:", error);
    });
  }, 5000);
});

// Add error handling for component errors
const handleComponentError = (error: Error, instance: any, info: string) => {
  console.error("Component error:", error, info);
  // You could show a user-friendly error message here
};

// Cleanup interval on unmount
onUnmounted(() => {
  if (refreshInterval) {
    clearInterval(refreshInterval);
  }
});
</script>
<template>
  <RSection icon="mdi-pulse" title="Tasks" class="ma-2">
    <template #toolbar-append />
    <template #content>
      <!-- Running Tasks Section -->
      <v-chip
        label
        variant="text"
        prepend-icon="mdi-play-circle"
        class="ml-2 mt-1"
      >
        Currently Running
      </v-chip>
      <v-divider class="border-opacity-25 ma-1" />

      <!-- Scan Progress Summary -->
      <div v-if="overallScanProgress" class="ma-3">
        <v-card variant="outlined" class="pa-3">
          <div class="d-flex align-center mb-2">
            <v-icon color="primary" class="mr-2">mdi-magnify-scan</v-icon>
            <span class="text-h6">Scan Progress</span>
          </div>
          <div class="mb-3">
            <div class="d-flex justify-space-between align-center mb-1">
              <span class="text-caption">Platforms</span>
              <span class="text-caption"
                >{{ overallScanProgress.platformProgress }}%</span
              >
            </div>
            <v-progress-linear
              :model-value="overallScanProgress.platformProgress"
              color="primary"
              height="8"
              rounded
            />
          </div>
          <div class="mb-3">
            <div class="d-flex justify-space-between align-center mb-1">
              <span class="text-caption">ROMs</span>
              <span class="text-caption"
                >{{ overallScanProgress.romProgress }}%</span
              >
            </div>
            <v-progress-linear
              :model-value="overallScanProgress.romProgress"
              color="secondary"
              height="8"
              rounded
            />
          </div>
          <div class="d-flex flex-wrap gap-2">
            <v-chip size="small" color="primary" variant="outlined">
              Platforms: {{ overallScanProgress.scannedPlatforms }}/{{
                overallScanProgress.totalPlatforms
              }}
            </v-chip>
            <v-chip size="small" color="secondary" variant="outlined">
              ROMs: {{ overallScanProgress.scannedRoms }}/{{
                overallScanProgress.totalRoms
              }}
            </v-chip>
            <v-chip size="small" color="success" variant="outlined">
              Added: {{ overallScanProgress.addedRoms }}
            </v-chip>
            <v-chip size="small" color="info" variant="outlined">
              Metadata: {{ overallScanProgress.metadataRoms }}
            </v-chip>
          </div>
        </v-card>
      </div>
      <div v-if="taskStatuses.length === 0" class="no-tasks-container">
        <v-card elevation="0" class="bg-background ma-3">
          <v-list-item>
            <template #prepend>
              <v-icon color="grey">mdi-information-outline</v-icon>
            </template>
            <v-list-item-title class="text-grey">
              No currently running tasks
            </v-list-item-title>
          </v-list-item>
        </v-card>
      </div>
      <div v-else class="tasks-grid">
        <div
          v-for="task in taskStatuses"
          :key="`task-${task.task_id}-${task.status}`"
          class="task-item"
        >
          <RunningTaskItem class="ma-3" :task="task" />
        </div>
      </div>

      <v-chip
        label
        variant="text"
        prepend-icon="mdi-folder-eye"
        class="ml-2 mt-1"
      >
        Watcher
      </v-chip>
      <v-divider class="border-opacity-25 ma-1" />
      <v-row no-gutters class="align-center py-1">
        <v-col v-for="task in watcherTasksUI" :key="task.name" cols="12" md="6">
          <TaskOption
            class="ma-3"
            :enabled="task.enabled"
            :title="task.title"
            :description="task.description"
            :icon="task.icon"
            :name="task.name"
            :manual-run="task.manual_run"
            :cron-string="task.cron_string"
          />
        </v-col>
      </v-row>

      <v-chip label variant="text" prepend-icon="mdi-clock" class="ml-2 mt-1">
        Scheduled
      </v-chip>
      <v-divider class="border-opacity-25 ma-1" />
      <v-row no-gutters class="align-center py-1">
        <v-col
          v-for="task in scheduledTasksUI"
          :key="task.name"
          cols="12"
          md="6"
        >
          <TaskOption
            class="ma-3"
            :enabled="task.enabled"
            :title="task.title"
            :description="task.description"
            :icon="task.icon"
            :name="task.name"
            :manual-run="task.manual_run"
            :cron-string="task.cron_string"
          />
        </v-col>
      </v-row>
      <v-row no-gutters class="align-center py-1">
        <v-chip
          label
          variant="text"
          prepend-icon="mdi-gesture-double-tap"
          class="ml-2 mt-1"
        >
          Manual
        </v-chip>
        <v-divider class="border-opacity-25 ma-1" />
        <v-col v-for="task in manualTasksUI" :key="task.name" cols="12" md="6">
          <TaskOption
            class="ma-3"
            :title="task.title"
            :description="task.description"
            :icon="task.icon"
            :name="task.name"
            :manual-run="task.manual_run"
            :cron-string="task.cron_string"
          />
        </v-col>
      </v-row>
    </template>
  </RSection>
</template>

<style scoped>
.tasks-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  grid-template-rows: masonry;
  gap: 0;
  margin: 0;
}

.task-item {
  min-height: 0;
}

.no-tasks-container {
  margin: 0;
}

/* Responsive design */
@media (max-width: 768px) {
  .tasks-grid {
    flex-direction: column;
  }
}
</style>
