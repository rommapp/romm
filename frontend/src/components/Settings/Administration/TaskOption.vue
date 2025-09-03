<script setup lang="ts">
import type { Emitter } from "mitt";
import { inject, computed } from "vue";
import taskApi from "@/services/api/task";
import storeRunningTasks from "@/stores/runningTasks";
import type { Events } from "@/types/emitter";

const props = withDefaults(
  defineProps<{
    enabled?: boolean;
    title?: string;
    description?: string;
    icon?: string;
    name?: string;
    manual_run?: boolean;
    cron_string?: string;
  }>(),
  {
    enabled: true,
    title: "",
    description: "",
    icon: "",
    name: "",
    manual_run: false,
    cron_string: "",
  },
);
const emitter = inject<Emitter<Events>>("emitter");
const runningTasksStore = storeRunningTasks();

// Computed properties
const isTaskRunning = computed(() =>
  props.name ? runningTasksStore.isTaskRunning(props.name) : false,
);

function run() {
  if (!props.name) return;

  // Add task to running tasks
  runningTasksStore.addTask(props.name);

  taskApi
    .runTask(props.name)
    .then(() => {
      emitter?.emit("snackbarShow", {
        msg: `Task '${props.title}' ran successfully!`,
        icon: "mdi-check-bold",
        color: "green",
      });
    })
    .catch((error) => {
      console.log(error);
      emitter?.emit("snackbarShow", {
        msg: error.response.data.detail,
        icon: "mdi-close-circle",
        color: "red",
      });
    })
    .finally(() => {
      // Remove task from running tasks
      runningTasksStore.removeTask(props.name);
    });
}
</script>
<template>
  <v-card elevation="0" class="bg-background">
    <v-row no-gutters>
      <v-col>
        <v-list-item :disabled="!enabled" class="pa-0">
          <template #prepend>
            <v-icon :class="enabled ? 'text-primary' : ''" :icon="icon" />
          </template>
          <v-list-item-title
            class="font-weight-bold"
            :class="{ 'text-primary': enabled }"
            >{{ title }}</v-list-item-title
          >
          <v-list-item-subtitle>{{ description }}</v-list-item-subtitle>
        </v-list-item>
      </v-col>
      <v-col v-if="manual_run" cols="auto" class="d-flex align-center">
        <v-btn
          variant="outlined"
          size="small"
          class="text-primary"
          :disabled="isTaskRunning"
          :loading="isTaskRunning"
          @click="run"
        >
          <v-icon>mdi-play</v-icon>
        </v-btn>
      </v-col>
    </v-row>
  </v-card>
</template>
