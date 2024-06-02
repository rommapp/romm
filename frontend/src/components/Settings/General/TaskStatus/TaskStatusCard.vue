<script setup lang="ts">
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { inject } from "vue";

import TaskScheduler from "@/components/Settings/General/TaskStatus/TaskScheduler.vue";
import TaskWatcher from "@/components/Settings/General/TaskStatus/TaskWatcher.vue";
import api from "@/services/api/index";
import storeHeartbeat from "@/stores/heartbeat";
import storeRunningTasks from "@/stores/runningTasks";

// Props
const emitter = inject<Emitter<Events>>("emitter");
const heartbeatStore = storeHeartbeat();
const runningTasks = storeRunningTasks();

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
    msg: result.data.msg,
    icon: "mdi-check-circle",
    color: "green",
  });
};
</script>
<template>
  <v-card rounded="0">
    <v-toolbar
      class="bg-terciary"
      density="compact"
    >
      <v-toolbar-title class="text-button">
        <v-icon class="mr-3">
          mdi-pulse
        </v-icon>
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
        <task-watcher :watcher="heartbeatStore.value.WATCHER" />

        <v-divider class="border-opacity-25" />

        <v-col
          v-for="task in heartbeatStore.value.SCHEDULER"
          :key="task.TITLE"
          cols="12"
          md="4"
          sm="6"
          class="status-item d-flex"
          :class="{
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
