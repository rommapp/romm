<script setup lang="ts">
import { computed } from "vue";
import { TaskStatusItem, type TaskStatusResponse } from "@/utils/tasks";
import TaskProgressDisplay from "./tasks/TaskProgressDisplay.vue";

const props = defineProps<{
  task: TaskStatusResponse;
}>();

const statusIconColor = computed(() => {
  return TaskStatusItem[props.task.status];
});

const taskDuration = computed(() => {
  if (!props.task.started_at) return null;
  if (props.task.status === "failed") return null;

  const startTime = new Date(props.task.started_at);
  const endTime = props.task.ended_at
    ? new Date(props.task.ended_at)
    : new Date();
  const duration = endTime.getTime() - startTime.getTime();

  if (duration < 1000) return "< 1s";
  if (duration < 60000) return `${Math.round(duration / 1000)}s`;
  if (duration < 3600000) return `${Math.round(duration / 60000)}m`;
  return `${Math.round(duration / 3600000)}h`;
});

const formatRunTime = () => {
  if (!props.task.started_at) return "Not started";

  const startTime = new Date(props.task.started_at);
  return startTime.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
};
</script>

<template>
  <v-card elevation="2" class="rounded">
    <v-card-text class="pa-0">
      <div class="d-flex align-center justify-space-between">
        <div class="d-flex align-center ga-2 flex-grow-1">
          <v-icon
            :color="statusIconColor.color"
            :icon="statusIconColor.icon"
            size="20"
            :class="{ 'task-icon--spinning': task.status === 'started' }"
          />
          <div class="d-flex flex-row flex-grow-1 ga-3">
            <h3 class="text-lg">
              {{ task.task_name }}
            </h3>
            <div class="d-flex align-center ga-2">
              <v-chip size="x-small" variant="tonal" class="text-caption">
                {{ task.task_type }}
              </v-chip>
              <v-chip
                v-if="taskDuration"
                size="x-small"
                variant="tonal"
                class="text-caption"
              >
                {{ taskDuration }}
              </v-chip>
            </div>
          </div>
        </div>
        <div class="d-flex align-center ga-2">
          <v-chip size="small" variant="tonal" class="text-caption">
            {{ formatRunTime() }}
          </v-chip>
          <v-chip
            :color="statusIconColor.color"
            size="small"
            variant="flat"
            class="font-weight-semibold text-capitalize"
          >
            <v-icon
              :icon="statusIconColor.icon"
              size="16"
              class="mr-1"
              :class="{ 'task-icon--spinning': task.status === 'started' }"
            />
            {{ task.status }}
          </v-chip>
        </div>
      </div>
    </v-card-text>

    <TaskProgressDisplay :task="task" />
  </v-card>
</template>

<style scoped>
.task-icon--spinning {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}
</style>
