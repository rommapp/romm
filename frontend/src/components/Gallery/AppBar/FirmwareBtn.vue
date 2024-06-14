<script setup lang="ts">
import storeGalleryFilter from "@/stores/galleryFilter";
import { inject, nextTick } from "vue";
import { useRoute } from "vue-router";
import type { Emitter } from "mitt";
import type { Events } from "@/types/emitter";
import storePlatforms, { type Platform } from "@/stores/platforms";
import { storeToRefs } from "pinia";

// Props
const galleryFilterStore = storeGalleryFilter();
const emitter = inject<Emitter<Events>>("emitter");
const { activeFirmwareDrawer } = storeToRefs(galleryFilterStore);
const platforms = storePlatforms();
const route = useRoute();
function showFirmwareDrawer() {
  nextTick(() =>
    emitter?.emit(
      "firmwareDrawerShow",
      platforms.get(Number(route.params.platform)) as Platform
    )
  );
  galleryFilterStore.switchActiveFirmwareDrawer();
}
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
        @click="showFirmwareDrawer" /></template
  ></v-tooltip>
</template>
