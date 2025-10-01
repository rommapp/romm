<script setup lang="ts">
import { computed } from "vue";
import type { TaskStatusResponse } from "@/__generated__";

const props = defineProps<{
  task: TaskStatusResponse;
}>();

const statusIcon = computed(() => {
  switch (props.task.status) {
    case "queued":
      return "mdi-clock-outline";
    case "started":
      return "mdi-loading";
    default:
      return "mdi-help-circle-outline";
  }
});

const statusColor = computed(() => {
  switch (props.task.status) {
    case "queued":
      return "orange";
    case "started":
      return "blue";
    default:
      return "grey";
  }
});

const formatDateTime = (dateTime: string | null) => {
  if (!dateTime) return "N/A";
  return new Date(dateTime).toLocaleString();
};
</script>

<template>
  <v-card elevation="0" class="bg-background">
    <v-row no-gutters>
      <v-col>
        <v-list-item class="pa-0">
          <template #prepend>
            <v-icon :color="statusColor" :icon="statusIcon" />
          </template>
          <v-list-item-title class="font-weight-bold">
            {{ task.task_name }}
          </v-list-item-title>
          <v-list-item-subtitle>
            <div class="d-flex flex-column">
              <span>Status: {{ task.status }}</span>
              <span v-if="task.queued_at">
                Queued: {{ formatDateTime(task.queued_at) }}
              </span>
              <span v-if="task.started_at">
                Started: {{ formatDateTime(task.started_at) }}
              </span>
            </div>
          </v-list-item-subtitle>
        </v-list-item>
      </v-col>
      <v-col cols="auto" class="d-flex align-center">
        <v-chip :color="statusColor" size="small" variant="outlined">
          {{ task.status }}
        </v-chip>
      </v-col>
    </v-row>
  </v-card>
</template>
