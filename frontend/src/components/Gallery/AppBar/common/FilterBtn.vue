<script setup lang="ts">
import storeGalleryFilter from "@/stores/galleryFilter";
import { storeToRefs } from "pinia";
import { useI18n } from "vue-i18n";

// Props
const { t } = useI18n();
const galleryFilterStore = storeGalleryFilter();
const { activeFilterDrawer } = storeToRefs(galleryFilterStore);
</script>

<template>
  <v-tooltip
    location="bottom"
    class="tooltip"
    transition="fade-transition"
    :text="t('platform.filter-gallery')"
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
        @click="galleryFilterStore.switchActiveFilterDrawer()" /></template
  ></v-tooltip>
</template>
