<script setup lang="ts">
import { useWalkthrough } from "@/composables/useWalkthrough";
import type { Walkthrough } from "@/composables/useWalkthrough";

defineProps<{
  walkthrough: Walkthrough;
}>();

const { getProgressLabel } = useWalkthrough({});
</script>

<template>
  <v-expansion-panel-title class="bg-toplayer">
    <div class="d-flex align-center">
      <v-chip size="x-small" class="mr-2" color="primary">
        {{ walkthrough.source }}
      </v-chip>
      <div class="d-flex flex-column">
        <span class="text-body-2 font-weight-medium">
          {{ walkthrough.title?.split("by")[0] || walkthrough.url }}
        </span>
        <div class="text-caption text-medium-emphasis">
          <span v-if="walkthrough.author">By {{ walkthrough.author }}</span>
          <span v-else>{{ walkthrough.url }}</span>
        </div>
      </div>
    </div>

    <template #actions>
      <div class="d-flex align-center">
        <v-chip size="x-small" color="primary" variant="tonal" class="ml-2">
          {{ getProgressLabel(walkthrough) }}
        </v-chip>
        <v-btn
          icon="mdi-open-in-new"
          variant="text"
          size="small"
          :href="walkthrough.url"
          target="_blank"
          class="mr-1"
        />
      </div>
    </template>
  </v-expansion-panel-title>
</template>
