<script setup>
import { inject, ref, onMounted } from "vue";
import { debounce } from "lodash";
import storeGalleryFilter from "@/stores/galleryFilter";

// Props
const galleryFilter = storeGalleryFilter();
const filterValue = ref("");

// Event listeners bus
const emitter = inject("emitter");
onMounted(() => {
  filterValue.value = galleryFilter.value;
});

function clearFilter() {
  galleryFilter.set("");
  emitter.emit("filter");
}

const filterRoms = debounce(() => {
  galleryFilter.set(filterValue.value);
  emitter.emit("filter");
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
