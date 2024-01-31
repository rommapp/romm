<script setup lang="ts">
import { views } from "@/utils";
import storeGalleryView from "@/stores/galleryView";

// Props
const galleryView = storeGalleryView();
</script>

<template>
  <v-tooltip
    location="bottom"
    class="tooltip"
    transition="fade-transition"
    text="Change view"
    open-delay="500"
    ><template v-slot:activator="{ props }">
      <v-btn
        @click="galleryView.next()"
        rounded="0"
        variant="text"
        v-bind="props"
        class="mr-0"
        :icon="views[galleryView.current]['icon']" /></template
  ></v-tooltip>
</template>
<style scoped>
.tooltip :deep(.v-overlay__content) {
  background: rgba(201, 201, 201, 0.98) !important;
  color: rgb(41, 41, 41) !important;
}
</style>
