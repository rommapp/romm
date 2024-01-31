<script setup lang="ts">
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { ref, inject } from "vue";

// Props
const emitter = inject<Emitter<Events>>("emitter");
const isShowFilterBar = ref(false);
function showFilterBar() {
  emitter?.emit("filterBarShow", null);
  isShowFilterBar.value = !isShowFilterBar.value;
}
</script>

<template>
  <v-tooltip
    location="bottom"
    class="tooltip"
    transition="fade-transition"
    text="Filter gallery"
    open-delay="500"
    ><template v-slot:activator="{ props }">
      <v-btn
        class="ml-0"
        variant="text"
        rounded="0"
        v-bind="props"
        icon="mdi-filter-variant"
        :color="isShowFilterBar ? 'romm-accent-1' : ''"
        @click="showFilterBar" /></template
  ></v-tooltip>
</template>
<style scoped>
.tooltip :deep(.v-overlay__content) {
  background: rgba(201, 201, 201, 0.98) !important;
  color: rgb(41, 41, 41) !important;
}
</style>
