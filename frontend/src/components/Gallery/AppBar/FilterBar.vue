<script setup lang="ts">
import { inject, ref, onMounted } from "vue";
import { debounce } from "lodash";
import type { Emitter } from "mitt";
import type { Events } from "@/types/emitter";

import storeGalleryFilter from "@/stores/galleryFilter";

// Props
const galleryFilter = storeGalleryFilter();
const filterValue = ref("");

// Event listeners bus
const emitter = inject<Emitter<Events>>("emitter");
onMounted(() => {
  filterValue.value = galleryFilter.filter;
});

function clearFilter() {
  galleryFilter.set("");
  emitter?.emit("filter", null);
}

const filterRoms = debounce(() => {
  galleryFilter.set(filterValue.value);
  emitter?.emit("filter", null);
}, 500);
</script>

<template>
  <v-text-field
    @click:clear="clearFilter"
    @keyup="filterRoms"
    v-model="filterValue"
    prepend-inner-icon="mdi-magnify"
    label="search"
    rounded="0"
    hide-details
    clearable
  />
</template>
