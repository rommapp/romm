<script setup lang="ts">
import storeGalleryView from "@/stores/galleryView";
import { storeToRefs } from "pinia";
import { useI18n } from "vue-i18n";

// Props
const { t } = useI18n();
const galleryViewStore = storeGalleryView();
const { activeFirmwareDrawer } = storeToRefs(galleryViewStore);
</script>

<template>
  <v-tooltip
    location="bottom"
    class="tooltip"
    transition="fade-transition"
    :text="t('platform.show-firmwares')"
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
