<script setup lang="ts">
import type { Events } from "@/types/emitter";
import { debounce } from "lodash";
import type { Emitter } from "mitt";
import { inject, onMounted, ref } from "vue";

import storeGalleryFilter from "@/stores/galleryFilter";

// Props
const galleryFilter = storeGalleryFilter();
const filterValue = ref("");

// Event listeners bus
const emitter = inject<Emitter<Events>>("emitter");

function clearFilter() {
  galleryFilter.set("");
  emitter?.emit("filter", null);
}

const filterRoms = debounce(() => {
  galleryFilter.set(filterValue.value);
  emitter?.emit("filter", null);
}, 500);

onMounted(() => {
  filterValue.value = galleryFilter.filter;
});
</script>

<template>
  <v-text-field
    @click:clear="clearFilter"
    @keyup="filterRoms"
    v-model="filterValue"
    prepend-inner-icon="mdi-filter-variant"
    label="Filter"
    rounded="0"
    hide-details
    clearable
  />
</template>
