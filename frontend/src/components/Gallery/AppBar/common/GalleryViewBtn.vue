<script setup lang="ts">
import storeGalleryView from "@/stores/galleryView";
import { views } from "@/utils";
import { useI18n } from "vue-i18n";

// Props
const { t } = useI18n();
const galleryView = storeGalleryView();
</script>

<template>
  <v-tooltip
    location="bottom"
    class="tooltip"
    transition="fade-transition"
    :text="t('platform.change-view')"
    open-delay="1000"
  >
    <template #activator="{ props }">
      <v-btn
        variant="text"
        v-bind="props"
        rounded="0"
        class="mr-0"
        :icon="views[galleryView.currentView]['icon']"
        aria-label="Change view"
        @click="galleryView.next()" /></template
  ></v-tooltip>
</template>
