<script setup lang="ts">
import { storeToRefs } from "pinia";
import { computed, onMounted, onUnmounted, ref } from "vue";
import RunningTaskItem from "@/components/Settings/Administration/RunningTaskItem.vue";
import TaskOption from "@/components/Settings/Administration/TaskOption.vue";
import RSection from "@/components/common/RSection.vue";
import storeTasks from "@/stores/tasks";
import { convertCronExperssion } from "@/utils";

const tasksStore = storeTasks();
const { watcherTasks, scheduledTasks, manualTasks, activeTasks } =
  storeToRefs(tasksStore);
const isLoadingRunningTasks = ref(false);

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

// Icon mapping for manual tasks
const getManualTaskIcon = (taskName: string) => {
  const iconMap: Record<string, string> = {
    cleanup_orphaned_resources: "mdi-broom",
  };
  return iconMap[taskName] || "mdi-play";
};

// Fetch running tasks
const fetchActiveTasks = async () => {
  isLoadingRunningTasks.value = true;
  try {
    await tasksStore.fetchActiveTasks();
  } catch (error) {
    console.error("Error fetching running tasks:", error);
  } finally {
    isLoadingRunningTasks.value = false;
  }
};

// Auto-refresh running tasks every 5 seconds
let refreshInterval: NodeJS.Timeout | null = null;

onMounted(() => {
  fetchActiveTasks();
  refreshInterval = setInterval(fetchActiveTasks, 5000);
});

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
      <v-row no-gutters class="align-center py-1">
        <v-col
          v-if="activeTasks.length === 0 && !isLoadingRunningTasks"
          cols="12"
        >
          <v-card elevation="0" class="bg-background ma-3">
            <v-list-item>
              <template #prepend>
                <v-icon color="grey">mdi-information-outline</v-icon>
              </template>
              <v-list-item-title class="text-grey">
                No tasks currently running
              </v-list-item-title>
            </v-list-item>
          </v-card>
        </v-col>
        <v-col v-else-if="isLoadingRunningTasks" cols="12">
          <v-card elevation="0" class="bg-background ma-3">
            <v-list-item>
              <template #prepend>
                <v-progress-circular indeterminate size="24" />
              </template>
              <v-list-item-title> Loading running tasks... </v-list-item-title>
            </v-list-item>
          </v-card>
        </v-col>
        <v-col
          v-else
          v-for="task in activeTasks"
          :key="task.task_id"
          cols="12"
          md="6"
        >
          <RunningTaskItem class="ma-3" :task="task" />
        </v-col>
      </v-row>

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
