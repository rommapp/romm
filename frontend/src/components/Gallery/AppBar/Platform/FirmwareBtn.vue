<script setup lang="ts">
import storeGalleryView from "@/stores/galleryView";
import { storeToRefs } from "pinia";

// Props
const galleryViewStore = storeGalleryView();
const { activeFirmwareDrawer } = storeToRefs(galleryViewStore);
</script>

<template>
  <v-tooltip
    location="bottom"
    class="tooltip"
    transition="fade-transition"
    text="Show firmwares/BIOS"
    open-delay="1000"
  >
    <template #activator="{ props }">
      <v-btn
        class="ml-0"
        variant="text"
        rounded="0"
        v-bind="props"
        icon="mdi-memory"
        :color="activeFirmwareDrawer ? 'romm-accent-1' : ''"
        @click="galleryViewStore.switchActiveFirmwareDrawer()" /></template
  ></v-tooltip>
</template>
