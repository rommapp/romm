<script setup lang="ts">
import storeGalleryFilter from "@/stores/galleryFilter";
import type { Events } from "@/types/emitter";
import { debounce } from "lodash";
import type { Emitter } from "mitt";
import { inject, onMounted, ref } from "vue";

// Props
const galleryFilter = storeGalleryFilter();
const filter = ref("");

// Event listeners bus
const emitter = inject<Emitter<Events>>("emitter");

// Functions
const filterRoms = debounce(() => {
  galleryFilter.setFilterSearch(filter?.value ?? "");
  emitter?.emit('filter', null);
}, 500);

onMounted(() => {
  filter.value = galleryFilter.filterSearch;
});
</script>

<template>
  <v-text-field
    v-model="filter"
    prepend-inner-icon="mdi-filter-outline"
    label="Filter"
    rounded="0"
    hide-details
    clearable
    @update:model-value="filterRoms"
  />
</template>
