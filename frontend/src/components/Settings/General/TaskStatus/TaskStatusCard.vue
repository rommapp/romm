<script setup lang="ts">
import { ref, onBeforeMount, inject } from "vue";
import type { Emitter } from "mitt";
import type { Events } from "@/types/emitter";

import { api } from "@/services/api";
import storeRunningTasks from "@/stores/runningTasks";
import TaskWatcher from "@/components/Settings/General/TaskStatus/TaskWatcher.vue";
import TaskScheduler from "@/components/Settings/General/TaskStatus/TaskScheduler.vue";
import storeHeartbeat from "@/stores/heartbeat";

// Props
const emitter = inject<Emitter<Events>>("emitter");
const heartbeat = storeHeartbeat();
const runningTasks = storeRunningTasks()

// Methods
const runAllTasks = async () => {
  runningTasks.value = true;
  const result = await api.post("/tasks/run");
  runningTasks.value = false;
  if (result.status !== 200) {
    return emitter?.emit("snackbarShow", {
      msg: "Error running tasks",
      icon: "mdi-close-circle",
      color: "red",
    });
  }

  emitter?.emit("snackbarShow", {
    msg: result.data.message,
    icon: "mdi-check-circle",
    color: "green",
  });
};
</script>
<template>
  <v-card rounded="0">
    <v-toolbar class="bg-terciary" density="compact">
      <v-toolbar-title class="text-button">
        <v-icon class="mr-3">mdi-pulse</v-icon>
        Task Status
      </v-toolbar-title>
      <v-btn
        :disabled="runningTasks.value"
        :loading="runningTasks.value"
        prepend-icon="mdi-play"
        variant="outlined"
        class="text-romm-accent-1"
        @click="runAllTasks"
      >
        Run All
      </v-btn>
    </v-toolbar>

    <v-divider class="border-opacity-25" />

    <v-card-text>
      <v-row>
        <task-watcher :watcher="heartbeat.data.WATCHER" />

        <v-divider class="border-opacity-25" />

        <v-col
          v-for="task in heartbeat.data.SCHEDULER"
          cols="12"
          md="4"
          sm="6"
          :class="{
            'status-item d-flex': true,
            disabled: !task.ENABLED,
          }"
        >
          <task-scheduler :task="task" />
        </v-col>
      </v-row>
    </v-card-text>
  </v-card>
</template>

<style scoped>
.status-item.disabled {
  opacity: 0.5;
}
</style>
