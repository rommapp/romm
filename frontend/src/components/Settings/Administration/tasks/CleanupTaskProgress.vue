<script setup lang="ts">
import type { CleanupStats } from "@/__generated__";

defineProps<{
  cleanupStats: CleanupStats;
}>();
</script>

<template>
  <div class="d-flex flex-wrap gap-2">
    <v-chip size="x-small" color="success" variant="outlined">
      Removed: {{ cleanupStats.removed }} items
    </v-chip>
  </div>
</template>
