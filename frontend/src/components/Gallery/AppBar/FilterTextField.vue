<script setup lang="ts">
import storeGalleryFilter from "@/stores/galleryFilter";
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import { debounce } from "lodash";
import { inject, nextTick } from "vue";

// Props
const emitter = inject<Emitter<Events>>("emitter");
const galleryFilterStore = storeGalleryFilter();
const { filterSearch } = storeToRefs(galleryFilterStore);
const filterRoms = debounce(() => {
  emitter?.emit("filter", null);
}, 500);
</script>

<template>
  <v-text-field
    v-model="filterSearch"
    prepend-inner-icon="mdi-filter-outline"
    label="Filter"
    rounded="0"
    hide-details
    clearable
    @update:model-value="nextTick(filterRoms)"
  />
</template>
