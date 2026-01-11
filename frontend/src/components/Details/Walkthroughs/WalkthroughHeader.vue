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
      <v-chip size="small" class="mr-2" color="primary">
        {{ walkthrough.source }}
      </v-chip>
      <div class="d-flex flex-column">
        <div class="text-body-2 font-weight-medium">
          {{ walkthrough.title || walkthrough.url }}
        </div>
        <div class="text-caption text-medium-emphasis">
          <span v-if="walkthrough.author">By {{ walkthrough.author }}</span>
          <span v-else>{{ walkthrough.url }}</span>
        </div>
      </div>
    </div>
    <v-chip size="x-small" color="primary" variant="tonal" class="ml-2">
      {{ getProgressLabel(walkthrough) }}
    </v-chip>
    <template #actions>
      <v-btn
        icon="mdi-open-in-new"
        variant="text"
        size="small"
        :href="walkthrough.url"
        target="_blank"
        class="mr-1"
      />
    </template>
  </v-expansion-panel-title>
</template>
