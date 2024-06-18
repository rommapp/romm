<script setup lang="ts">
import Task from "@/components/Settings/TaskOption.vue";
import RSection from "@/components/common/RSection.vue";
import api from "@/services/api/index";
import storeHeartbeat from "@/stores/heartbeat";
import storeRunningTasks from "@/stores/runningTasks";
import type { Events } from "@/types/emitter";
import { convertCronExperssion } from "@/utils";
import type { Emitter } from "mitt";
import { computed, inject } from "vue";

// Props
const emitter = inject<Emitter<Events>>("emitter");
const heartbeatStore = storeHeartbeat();
const runningTasks = storeRunningTasks();

const tasks = computed(() => [
  {
    title: heartbeatStore.value.WATCHER.TITLE,
    description: heartbeatStore.value.WATCHER.MESSAGE,
    icon: heartbeatStore.value.WATCHER.ENABLED
      ? "mdi-file-check-outline"
      : "mdi-file-remove-outline",
    enabled: heartbeatStore.value.WATCHER.ENABLED,
  },
  {
    title: heartbeatStore.value.SCHEDULER.RESCAN.TITLE,
    description:
      heartbeatStore.value.SCHEDULER.RESCAN.MESSAGE +
      convertCronExperssion(heartbeatStore.value.SCHEDULER.RESCAN.CRON),
    icon: heartbeatStore.value.SCHEDULER.RESCAN.ENABLED
      ? "mdi-clock-check-outline"
      : "mdi-clock-remove-outline",
    enabled: heartbeatStore.value.SCHEDULER.RESCAN.ENABLED,
  },
  {
    title: heartbeatStore.value.SCHEDULER.SWITCH_TITLEDB.TITLE,
    description:
      heartbeatStore.value.SCHEDULER.SWITCH_TITLEDB.MESSAGE +
      convertCronExperssion(heartbeatStore.value.SCHEDULER.SWITCH_TITLEDB.CRON),
    icon: heartbeatStore.value.SCHEDULER.SWITCH_TITLEDB.ENABLED
      ? "mdi-clock-check-outline"
      : "mdi-clock-remove-outline",
    enabled: heartbeatStore.value.SCHEDULER.SWITCH_TITLEDB.ENABLED,
  },
]);

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
  <r-section icon="mdi-pulse" title="Tasks">
    <template #toolbar-append>
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
    </template>
    <template #content>
      <v-row no-gutters class="align-center">
        <v-col cols="12" md="6" v-for="task in tasks">
          <task
            class="ma-3"
            :enabled="task.enabled"
            :title="task.title"
            :description="task.description"
            :icon="task.icon"
          />
        </v-col>
      </v-row>
    </template>
  </r-section>
</template>
