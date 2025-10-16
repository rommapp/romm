<script setup lang="ts">
import { storeToRefs } from "pinia";
import { computed, nextTick, onMounted, onUnmounted } from "vue";
import { useI18n } from "vue-i18n";
import RunningTaskItem from "@/components/Settings/Administration/RunningTaskItem.vue";
import TaskOption from "@/components/Settings/Administration/TaskOption.vue";
import RSection from "@/components/common/RSection.vue";
import storeTasks from "@/stores/tasks";
import { convertCronExperssion } from "@/utils";

const { t } = useI18n();

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
    icon: "mdi-broom",
  })),
);

const fetchTaskStatus = async () => {
  try {
    await tasksStore.fetchTaskStatus();
    await nextTick();
  } catch (error) {
    console.error("Error fetching task status:", error);
  }
};

// Auto-refresh task status every 5 seconds
let refreshInterval: number | null = null;

onMounted(() => {
  fetchTaskStatus();
  refreshInterval = window.setInterval(() => {
    fetchTaskStatus().catch((error) => {
      console.error("Error in task status refresh:", error);
    });
  }, 5000);
});

onUnmounted(() => {
  if (refreshInterval) clearInterval(refreshInterval);
});
</script>
<template>
  <RSection icon="mdi-pulse" :title="t('settings.tasks')" class="ma-2">
    <template #toolbar-append />
    <template #content>
      <v-chip
        label
        variant="text"
        prepend-icon="mdi-folder-eye"
        class="ml-2 mt-1"
      >
        {{ t("settings.watcher") }}
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
        {{ t("settings.scheduled") }}
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

      <v-chip
        label
        variant="text"
        prepend-icon="mdi-gesture-double-tap"
        class="ml-2 mt-1"
      >
        {{ t("settings.manual") }}
      </v-chip>
      <v-divider class="border-opacity-25 ma-1" />
      <v-row no-gutters class="align-center py-1">
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

      <v-chip
        label
        variant="text"
        prepend-icon="mdi-play-circle"
        class="ml-2 mt-1"
      >
        {{ t("settings.task-history") }}
      </v-chip>
      <v-divider class="border-opacity-25 ma-1" />

      <v-row no-gutters v-if="taskStatuses.length === 0">
        <v-card elevation="0" class="bg-background ma-3">
          <v-list-item>
            <template #prepend>
              <v-icon color="grey">mdi-information-outline</v-icon>
            </template>
            <v-list-item-title class="text-grey">
              {{ t("settings.no-tasks-in-history") }}
            </v-list-item-title>
          </v-list-item>
        </v-card>
      </v-row>
      <v-row no-gutters v-else>
        <v-col
          cols="12"
          v-for="task in taskStatuses"
          :key="`task-${task.task_id}-${task.status}`"
        >
          <RunningTaskItem class="ma-1 pa-2" :task="task" />
        </v-col>
      </v-row>
    </template>
  </RSection>
</template>
