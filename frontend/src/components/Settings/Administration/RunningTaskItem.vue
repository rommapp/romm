<script setup lang="ts">
import {
  formatDistanceToNow,
  intervalToDuration,
  formatDuration,
} from "date-fns";
import { computed } from "vue";
import { formatTimestamp } from "@/utils";
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
  if (!props.task.ended_at && props.task.status === "failed") return null;
  if (
    props.task.ended_at &&
    new Date(props.task.started_at) >= new Date(props.task.ended_at)
  ) {
    return null;
  }

  const duration = intervalToDuration({
    start: new Date(props.task.started_at),
    end: props.task.ended_at ? new Date(props.task.ended_at) : new Date(),
  });

  return formatDuration(duration);
});

const taskDistanceFromNow = computed(() => {
  if (
    !props.task.started_at ||
    !props.task.enqueued_at ||
    !props.task.created_at
  )
    return null;
  return formatDistanceToNow(
    new Date(
      props.task.started_at || props.task.enqueued_at || props.task.created_at,
    ),
    { addSuffix: true },
  );
});
</script>

<template>
  <v-card elevation="2" class="rounded relative">
    <v-card-text class="pa-0">
      <div class="d-flex align-center justify-space-between">
        <div class="d-flex align-center ga-2">
          <v-icon
            :color="statusIconColor.color"
            :icon="statusIconColor.icon"
            size="18"
            :class="{ 'task-icon--spinning': task.status === 'started' }"
          />
          <div class="d-flex flex-row ga-3">
            <h3 class="text-body-1">
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
          <v-chip
            size="small"
            variant="tonal"
            class="text-caption"
            :title="
              formatTimestamp(
                task.started_at || task.enqueued_at || task.created_at,
              )
            "
          >
            {{ taskDistanceFromNow }}
          </v-chip>
          <v-chip
            :color="statusIconColor.color"
            size="small"
            variant="flat"
            class="text-capitalize"
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
