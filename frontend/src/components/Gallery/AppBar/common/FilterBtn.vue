<script setup lang="ts">
import { storeToRefs } from "pinia";
import { useI18n } from "vue-i18n";
import storeGalleryFilter from "@/stores/galleryFilter";
import storeRoms from "@/stores/roms";

const { t } = useI18n();
const galleryFilterStore = storeGalleryFilter();
const { activeFilterDrawer } = storeToRefs(galleryFilterStore);
const romsStore = storeRoms();
const { fetchTotalRoms } = storeToRefs(romsStore);
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
        class="ml-0 px-3 min-w-auto! h-full!"
        variant="text"
        rounded="0"
        v-bind="props"
        :color="
          activeFilterDrawer
            ? 'primary'
            : galleryFilterStore.isFiltered()
              ? 'secondary'
              : ''
        "
        aria-label="Filter"
        @click="galleryFilterStore.switchActiveFilterDrawer"
      >
        <div class="d-flex flex-col align-center">
          <span v-if="fetchTotalRoms > 0" class="text-caption leading-none!">{{
            fetchTotalRoms
          }}</span>
          <v-icon size="x-large">mdi-filter-variant</v-icon>
        </div>
      </v-btn>
    </template>
  </v-tooltip>
</template>
