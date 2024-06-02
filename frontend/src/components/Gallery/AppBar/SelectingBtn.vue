<script setup lang="ts">
import storeRoms from "@/stores/roms";

// Props
const romsStore = storeRoms();
</script>

<template>
  <v-tooltip
    location="bottom"
    class="tooltip"
    transition="fade-transition"
    text="Active multi-select"
    open-delay="1000"
  >
    <template #activator="{ props }">
      <v-btn
        :color="romsStore.selecting ? 'romm-accent-1' : ''"
        rounded="0"
        variant="text"
        v-bind="props"
        class="mr-0"
        icon="mdi-select-group"
        @click="romsStore.isSelecting()"
      />
    </template>
  </v-tooltip>
</template>
<style scoped>
.tooltip :deep(.v-overlay__content) {
  background: rgba(201, 201, 201, 0.98) !important;
  color: rgb(41, 41, 41) !important;
}
</style>
