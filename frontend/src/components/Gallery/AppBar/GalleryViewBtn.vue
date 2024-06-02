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
    open-delay="1000"
    ><template #activator="{ props }">
      <v-btn
        @click="galleryView.next()"
        rounded="0"
        variant="text"
        v-bind="props"
        class="mr-0"
        :icon="views[galleryView.current]['icon']" /></template
  ></v-tooltip>
</template>