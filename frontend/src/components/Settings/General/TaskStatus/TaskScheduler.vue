<script setup>
import { convertCronExperssion } from "@/utils/utils";

const props = defineProps(["scheduler"]);
const cronExpression = convertCronExperssion(props.scheduler.CRON);
</script>
<template>
  <v-icon
    :class="scheduler.ENABLED ? 'text-romm-accent-1' : ''"
    :icon="
      scheduler.ENABLED ? 'mdi-clock-check-outline' : 'mdi-clock-remove-outline'
    "
  />
  <div class="ml-3">
    <span
      class="font-weight-bold text-body-1"
      :class="scheduler.ENABLED ? 'text-romm-accent-1' : ''"
      >{{ scheduler.TITLE }}</span
    >
    <p class="mt-1">
      {{ scheduler.MESSAGE }}
      {{ cronExpression }}
    </p>
  </div>
</template>
