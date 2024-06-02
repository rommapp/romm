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
    open-delay="1000"
    ><template #activator="{ props }">
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