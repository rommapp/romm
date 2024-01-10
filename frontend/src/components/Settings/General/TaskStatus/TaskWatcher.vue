<script setup lang="ts">
import type { Heartbeat } from "@/stores/heartbeat";

defineProps<{ watcher: Heartbeat["WATCHER"] }>();
</script>
<template>
  <v-col
    cols="12"
    md="4"
    sm="4"
    lg="4"
    class="status-item d-flex"
    :class="{
      disabled: !watcher?.ENABLED,
    }"
  >
    <v-icon
      :class="watcher?.ENABLED ? 'text-romm-accent-1' : ''"
      :icon="
        watcher?.ENABLED ? 'mdi-file-check-outline' : 'mdi-file-remove-outline'
      "
    />
    <div class="ml-3">
      <span
        class="font-weight-bold text-body-1"
        :class="watcher?.ENABLED ? 'text-romm-accent-1' : ''"
        >{{ watcher?.TITLE }}</span
      >
      <p class="mt-1">
        {{ watcher?.MESSAGE }}
      </p>
    </div>
  </v-col>
</template>
