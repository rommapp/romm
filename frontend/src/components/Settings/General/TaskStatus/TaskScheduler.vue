<script setup>
import { convertCronExperssion } from "@/utils/utils";

const props = defineProps(["task"]);
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
      >{{ task.TITLE }}</span
    >
    <p class="mt-1">
      {{ task.MESSAGE }}
      {{ cronExpression }}
    </p>
  </div>
</template>
