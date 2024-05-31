<script setup lang="ts">
import FilterUnmatchedBtn from "@/components/Gallery/AppBar/FilterUnmatchedBtn.vue";
import storeGalleryFilter from "@/stores/galleryFilter";
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import { inject, ref, nextTick } from "vue";

// Props
const showFilterBar = ref(false);
const emitter = inject<Emitter<Events>>("emitter");
emitter?.on("filterBarShow", () => {
  showFilterBar.value = !showFilterBar.value;
});
emitter?.on("filterBarReset", () => {});

const galleryFilterStore = storeGalleryFilter();
const {
  selectedGenre,
  selectedFranchise,
  selectedCollection,
  selectedCompany,
} = storeToRefs(galleryFilterStore);
</script>

<template>
  <div v-if="showFilterBar">
    <v-row no-gutters class="pa-1">
      <filter-unmatched-btn />
      <v-autocomplete
        hide-details
        clearable
        label="Genre"
        density="compact"
        variant="outlined"
        class="ma-1"
        @update:model-value="nextTick(() => emitter?.emit('filter', null))"
        v-model="selectedGenre"
        :items="galleryFilterStore.filterGenres"
      ></v-autocomplete>
      <v-autocomplete
        hide-details
        clearable
        label="Franchise"
        density="compact"
        variant="outlined"
        class="ma-1"
        @update:model-value="nextTick(() => emitter?.emit('filter', null))"
        v-model="selectedFranchise"
        :items="galleryFilterStore.filterFranchises"
      ></v-autocomplete>
      <v-autocomplete
        hide-details
        clearable
        label="Collection"
        density="compact"
        variant="outlined"
        class="ma-1"
        @update:model-value="nextTick(() => emitter?.emit('filter', null))"
        v-model="selectedCollection"
        :items="galleryFilterStore.filterCollections"
      ></v-autocomplete>
      <v-autocomplete
        hide-details
        clearable
        label="Company"
        density="compact"
        variant="outlined"
        class="ma-1"
        @update:model-value="nextTick(() => emitter?.emit('filter', null))"
        v-model="selectedCompany"
        :items="galleryFilterStore.filterCompanies"
      ></v-autocomplete>
    </v-row>
    <v-divider
      :thickness="2"
      class="mx-2 border-opacity-25"
      color="romm-accent-1"
    />
  </div>
</template>
