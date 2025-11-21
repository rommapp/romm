<script setup lang="ts">
import { computed } from "vue";
import type {
  ScanStats,
  ConversionStats,
  CleanupStats,
  UpdateStats,
  ScanTaskStatusResponse,
  ConversionTaskStatusResponse,
  CleanupTaskStatusResponse,
  UpdateTaskStatusResponse,
} from "@/__generated__";
import { type TaskStatusResponse } from "@/utils/tasks";
import CleanupTaskProgress from "./CleanupTaskProgress.vue";
import ConversionTaskProgress from "./ConversionTaskProgress.vue";
import ScanTaskProgress from "./ScanTaskProgress.vue";
import UpdateTaskProgress from "./UpdateTaskProgress.vue";

const props = defineProps<{
  task: TaskStatusResponse;
}>();

const scanStats = computed((): ScanStats | null => {
  if (props.task.task_type !== "scan") return null;
  // @ts-ignore
  return props.task.meta?.scan_stats || null;
});

const conversionStats = computed((): ConversionStats | null => {
  if (props.task.task_type !== "conversion") return null;
  // @ts-ignore
  return props.task.meta?.conversion_stats || null;
});

const cleanupStats = computed((): CleanupStats | null => {
  if (props.task.task_type !== "cleanup") return null;
  // @ts-ignore
  return props.task.meta?.cleanup_stats || null;
});

const updateStats = computed((): UpdateStats | null => {
  if (props.task.task_type !== "update") return null;
  // @ts-ignore
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
</script>

<template>
  <v-card
    v-if="hasDetailedStats"
    elevation="0"
    rounded="0"
    class="position-static"
  >
    <v-card-text class="pa-0">
      <ScanTaskProgress
        v-if="task.task_type === 'scan' && scanStats"
        :task="task as ScanTaskStatusResponse"
        :scan-stats="scanStats"
      />
      <ConversionTaskProgress
        v-else-if="task.task_type === 'conversion' && conversionStats"
        :task="task as ConversionTaskStatusResponse"
        :conversion-stats="conversionStats"
      />
      <CleanupTaskProgress
        v-else-if="task.task_type === 'cleanup' && cleanupStats"
        :task="task as CleanupTaskStatusResponse"
        :cleanup-stats="cleanupStats"
      />
      <UpdateTaskProgress
        v-else-if="task.task_type === 'update' && updateStats"
        :task="task as UpdateTaskStatusResponse"
        :update-stats="updateStats"
      />
    </v-card-text>
  </v-card>
</template>
