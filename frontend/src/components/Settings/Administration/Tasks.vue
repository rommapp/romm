<script setup lang="ts">
import Task from "@/components/Settings/Administration/TaskOption.vue";
import RSection from "@/components/common/RSection.vue";
import api from "@/services/api/index";
import type { TaskInfoDict } from "@/__generated__/models/TaskInfoDict";
import { convertCronExperssion } from "@/utils";
import { computed, onMounted, ref } from "vue";

// Props
const tasks = ref<{
  watcher?: Array<TaskInfoDict>;
  scheduled?: Array<TaskInfoDict>;
  manual?: Array<TaskInfoDict>;
}>({});

const watcherTasks = computed(
  () =>
    tasks.value.watcher?.map((task) => ({
      title: task.title,
      description: task.description,
      icon: task.enabled ? "mdi-file-check-outline" : "mdi-file-remove-outline",
      enabled: task.enabled,
      name: task.name,
    })) || [],
);

const scheduledTasks = computed(
  () =>
    tasks.value.scheduled?.map((task) => ({
      title: task.title,
      description:
        task.description + " " + convertCronExperssion(task.cron_string),
      icon: task.enabled
        ? "mdi-clock-check-outline"
        : "mdi-clock-remove-outline",
      enabled: task.enabled,
      name: task.name,
      manual_run: task.manual_run,
      cron_string: convertCronExperssion(task.cron_string),
    })) || [],
);

// Icon mapping for manual tasks
const getManualTaskIcon = (taskName: string) => {
  const iconMap: Record<string, string> = {
    cleanup_orphaned_resources: "mdi-broom",
  };
  return iconMap[taskName] || "mdi-play";
};

const manualTasks = computed(
  () =>
    tasks.value.manual?.map((task) => ({
      title: task.title,
      description: task.description,
      icon: getManualTaskIcon(task.name),
      name: task.name,
      manual_run: task.manual_run,
    })) || [],
);

// Functions
const getAvailableTasks = async () => {
  await api.get("/tasks").then((response) => {
    tasks.value = response.data;
  });
  console.log(tasks.value);
};

onMounted(() => {
  getAvailableTasks();
});
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
        >Watcher</v-chip
      >
      <v-divider class="border-opacity-25 ma-1" />
      <v-row no-gutters class="align-center py-1">
        <v-col cols="12" md="6" v-for="task in watcherTasks">
          <task
            class="ma-3"
            :enabled="task.enabled"
            :title="task.title"
            :description="task.description"
            :icon="task.icon"
          />
        </v-col>
      </v-row>

      <v-chip label variant="text" prepend-icon="mdi-clock" class="ml-2 mt-1"
        >Scheduled</v-chip
      >
      <v-divider class="border-opacity-25 ma-1" />
      <v-row no-gutters class="align-center py-1">
        <v-col cols="12" md="6" v-for="task in scheduledTasks">
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
          >Manual</v-chip
        >
        <v-divider class="border-opacity-25 ma-1" />
        <v-col cols="12" md="6" v-for="task in manualTasks">
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
