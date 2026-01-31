<script setup lang="ts">
import { useWalkthrough } from "@/composables/useWalkthrough";
import type { Walkthrough } from "@/composables/useWalkthrough";

defineProps<{
  walkthrough: Walkthrough;
}>();

const { getProgressDisplay } = useWalkthrough({});
</script>
<template>
  <div
    class="d-flex flex-column align-end gap-1"
    v-if="walkthrough.format !== 'pdf'"
  >
    <div class="d-flex align-center gap-1">
      <span class="text-caption text-medium-emphasis">
        {{ getProgressDisplay(walkthrough).text }}
      </span>
      <v-progress-circular
        :model-value="getProgressDisplay(walkthrough).value"
        :color="getProgressDisplay(walkthrough).color"
        size="20"
      />
    </div>
  </div>
</template>
