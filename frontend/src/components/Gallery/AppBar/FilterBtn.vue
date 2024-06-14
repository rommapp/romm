<script setup lang="ts">
import storeGalleryFilter from "@/stores/galleryFilter";
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import { inject, nextTick } from "vue";

// Props
const galleryFilterStore = storeGalleryFilter();
const emitter = inject<Emitter<Events>>("emitter");
const { activeFilterDrawer } = storeToRefs(galleryFilterStore);
function showFilterDrawer() {
  nextTick(() => emitter?.emit("filterDrawerShow", null));
  galleryFilterStore.switchActiveFilterDrawer();
}
</script>

<template>
  <v-tooltip
    location="bottom"
    class="tooltip"
    transition="fade-transition"
    text="Filter gallery"
    open-delay="1000"
  >
    <template #activator="{ props }">
      <v-btn
        class="ml-0"
        variant="text"
        rounded="0"
        v-bind="props"
        icon="mdi-filter-variant"
        :color="activeFilterDrawer ? 'romm-accent-1' : ''"
        @click="showFilterDrawer" /></template
  ></v-tooltip>
</template>
