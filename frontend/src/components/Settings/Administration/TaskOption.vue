<script setup lang="ts">
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import { inject, computed } from "vue";
import taskApi from "@/services/api/task";
import storeTasks from "@/stores/tasks";
import type { Events } from "@/types/emitter";

const props = withDefaults(
  defineProps<{
    enabled?: boolean;
    title?: string;
    description?: string;
    icon?: string;
    name?: string;
    manualRun?: boolean;
    cronString?: string;
  }>(),
  {
    enabled: true,
    title: "",
    description: "",
    icon: "",
    name: "",
    manualRun: false,
    cronString: "",
  },
);
const emitter = inject<Emitter<Events>>("emitter");
const tasksStore = storeTasks();
const { taskStatuses } = storeToRefs(tasksStore);
const task = computed(() =>
  taskStatuses.value
    .filter((task) => !["queued", "started"].includes(task.status))
    .find((task) => task.task_name === props.name),
);

function run() {
  if (!props.name) return;

  taskApi
    .runTask(props.name)
    .then(() => {
      emitter?.emit("snackbarShow", {
        msg: `Task '${props.title}' started...`,
        icon: "mdi-check-bold",
        color: "green",
      });
    })
    .catch((error) => {
      console.error(error);
      emitter?.emit("snackbarShow", {
        msg: error.response.data.detail,
        icon: "mdi-close-circle",
        color: "red",
      });
    })
    .finally(() => {});
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
          >
            {{ title }}
          </v-list-item-title>
          <v-list-item-subtitle>{{ description }}</v-list-item-subtitle>
        </v-list-item>
      </v-col>
      <v-col v-if="manualRun" cols="auto" class="d-flex align-center">
        <v-btn
          variant="outlined"
          size="small"
          class="text-primary"
          :disabled="!!task"
          :loading="false"
          @click="run"
        >
          <v-icon>mdi-play</v-icon>
        </v-btn>
      </v-col>
    </v-row>
  </v-card>
</template>
