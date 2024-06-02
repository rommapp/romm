<script setup lang="ts">
import type { HeartbeatResponse } from "@/__generated__"
import { convertCronExperssion } from "@/utils";

type Scheduler = HeartbeatResponse["SCHEDULER"];

const props = defineProps<{ task: Scheduler[keyof Scheduler] }>();
const cronExpression = convertCronExperssion(props.task.CRON);
</script>
<template>
  <v-icon
    :class="task.ENABLED ? 'text-romm-accent-1' : ''"
    :icon="
      task.ENABLED ? 'mdi-clock-check-outline' : 'mdi-clock-remove-outline'
    "
  />
  <div class="ml-3">
    <span
      class="font-weight-bold text-body-1"
      :class="task.ENABLED ? 'text-romm-accent-1' : ''"
    >{{ task.TITLE }}</span>
    <p class="mt-1">
      {{ task.MESSAGE }}
      {{ cronExpression }}
    </p>
  </div>
</template>
