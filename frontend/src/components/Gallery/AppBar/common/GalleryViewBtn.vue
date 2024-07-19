<script setup lang="ts">
import storeGalleryView from "@/stores/galleryView";
import { views } from "@/utils";

// Props
const galleryView = storeGalleryView();
</script>

<template>
  <v-tooltip
    location="bottom"
    class="tooltip"
    transition="fade-transition"
    text="Change view"
    open-delay="1000"
  >
    <template #activator="{ props }">
      <v-btn
        rounded="0"
        variant="text"
        v-bind="props"
        class="mr-0"
        :icon="views[galleryView.currentView]['icon']"
        @click="galleryView.next()" /></template
  ></v-tooltip>
</template>
