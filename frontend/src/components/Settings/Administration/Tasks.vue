<script setup lang="ts">
import { storeToRefs } from "pinia";
import { computed } from "vue";
import Task from "@/components/Settings/Administration/TaskOption.vue";
import RSection from "@/components/common/RSection.vue";
import storeTasks from "@/stores/tasks";
import { convertCronExperssion } from "@/utils";

const tasksStore = storeTasks();
const { watcherTasks, scheduledTasks, manualTasks } = storeToRefs(tasksStore);

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
</script>
<template>
  <r-section icon="mdi-pulse" title="Tasks" class="ma-2">
    <template #toolbar-append> </template>
    <template #content>
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
        <v-col cols="12" md="6" v-for="task in watcherTasksUI">
          <task
            class="ma-3"
            :enabled="task.enabled"
            :title="task.title"
            :description="task.description"
            :icon="task.icon"
          />
        </v-col>
      </v-row>

      <v-chip label variant="text" prepend-icon="mdi-clock" class="ml-2 mt-1">
        Scheduled
      </v-chip>
      <v-divider class="border-opacity-25 ma-1" />
      <v-row no-gutters class="align-center py-1">
        <v-col cols="12" md="6" v-for="task in scheduledTasksUI">
          <task
            class="ma-3"
            :enabled="task.enabled"
            :title="task.title"
            :description="task.description"
            :icon="task.icon"
            :name="task.name"
            :manual_run="task.manual_run"
            :cron_string="task.cron_string"
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
        <v-col cols="12" md="6" v-for="task in manualTasksUI">
          <task
            class="ma-3"
            :title="task.title"
            :description="task.description"
            :icon="task.icon"
            :name="task.name"
            :manual_run="task.manual_run"
          />
        </v-col>
      </v-row>
    </template>
  </r-section>
</template>
