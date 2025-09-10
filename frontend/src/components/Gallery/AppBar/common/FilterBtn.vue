<script setup lang="ts">
import { storeToRefs } from "pinia";
import { useI18n } from "vue-i18n";
import storeGalleryFilter from "@/stores/galleryFilter";

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
        :color="
          activeFilterDrawer
            ? 'primary'
            : galleryFilterStore.isFiltered()
              ? 'secondary'
              : ''
        "
        aria-label="Filter"
        @click="galleryFilterStore.switchActiveFilterDrawer"
      />
    </template>
  </v-tooltip>
</template>
