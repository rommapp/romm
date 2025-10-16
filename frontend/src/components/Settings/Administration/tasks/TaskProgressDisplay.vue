<script setup lang="ts">
import { computed } from "vue";
import type {
  ScanStats,
  ConversionStats,
  CleanupStats,
  UpdateStats,
} from "@/__generated__";
import {
  TaskStatusItem,
  TaskTypeItem,
  type TaskStatusResponse,
} from "@/utils/tasks";
import CleanupTaskProgress from "./CleanupTaskProgress.vue";
import ConversionTaskProgress from "./ConversionTaskProgress.vue";
import ScanTaskProgress from "./ScanTaskProgress.vue";
import UpdateTaskProgress from "./UpdateTaskProgress.vue";

const props = defineProps<{
  task: TaskStatusResponse;
}>();

const scanStats = computed((): ScanStats | null => {
  if (props.task.task_type !== "scan") return null;
  return props.task.meta?.scan_stats || null;
});

const conversionStats = computed((): ConversionStats | null => {
  if (props.task.task_type !== "conversion") return null;
  return props.task.meta?.conversion_stats || null;
});

const cleanupStats = computed((): CleanupStats | null => {
  if (props.task.task_type !== "cleanup") return null;
  return props.task.meta?.cleanup_stats || null;
});

const updateStats = computed((): UpdateStats | null => {
  if (props.task.task_type !== "update") return null;
  return props.task.meta?.update_stats || null;
});

const hasDetailedStats = computed(() => {
  return !!(
    scanStats.value ||
    conversionStats.value ||
    cleanupStats.value ||
    updateStats.value
  );
});

const taskTypeItem = computed(() => {
  return TaskTypeItem[props.task.task_type];
});

const taskStatusItem = computed(() => {
  return TaskStatusItem[props.task.status];
});
</script>

<template>
  <v-card
    v-if="hasDetailedStats"
    elevation="0"
    class="mt-4 rounded border"
    variant="tonal"
  >
    <v-card-text class="pa-0">
      <div
        class="d-flex align-center justify-space-between pa-4 bg-grey-lighten-5"
      >
        <div
          class="d-flex align-center text-h6 font-weight-semibold text-grey-darken-2"
        >
          <v-icon :icon="taskTypeItem.icon" size="18" class="mr-2" />
          {{ taskTypeItem.title }}
        </div>
        <v-chip
          :color="taskStatusItem.color"
          size="small"
          variant="flat"
          class="font-weight-semibold text-capitalize"
        >
          {{ taskStatusItem.text }}
        </v-chip>
      </div>

      <div class="pa-4">
        <ScanTaskProgress
          v-if="task.task_type === 'scan' && scanStats"
          :scan-stats="scanStats"
        />
        <ConversionTaskProgress
          v-else-if="task.task_type === 'conversion' && conversionStats"
          :conversion-stats="conversionStats"
        />
        <CleanupTaskProgress
          v-else-if="task.task_type === 'cleanup' && cleanupStats"
          :cleanup-stats="cleanupStats"
        />
        <UpdateTaskProgress
          v-else-if="task.task_type === 'update' && updateStats"
          :update-stats="updateStats"
        />
      </div>
    </v-card-text>
  </v-card>
</template>
