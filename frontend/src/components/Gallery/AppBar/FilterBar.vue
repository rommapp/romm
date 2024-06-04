<script setup lang="ts">
import FilterUnmatchedBtn from "@/components/Gallery/AppBar/FilterUnmatchedBtn.vue";
import storeGalleryFilter from "@/stores/galleryFilter";
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import { inject, nextTick, ref } from "vue";

// Props
const showFilterBar = ref(false);
const emitter = inject<Emitter<Events>>("emitter");
emitter?.on("filterBarShow", () => {
  showFilterBar.value = !showFilterBar.value;
});

const galleryFilterStore = storeGalleryFilter();
const {
  selectedGenre,
  selectedFranchise,
  selectedCollection,
  selectedCompany,
} = storeToRefs(galleryFilterStore);
</script>

<template>
  <!-- TODO: try secondary drawer to filter -->
  <v-app-bar v-if="showFilterBar" elevation="0" density="comfortable">
    <v-row no-gutters class="px-1">
      <filter-unmatched-btn />
      <v-autocomplete
        v-model="selectedGenre"
        hide-details
        clearable
        label="Genre"
        density="compact"
        variant="outlined"
        class="ma-1"
        :items="galleryFilterStore.filterGenres"
        @update:model-value="nextTick(() => emitter?.emit('filter', null))"
      />
      <v-autocomplete
        v-model="selectedFranchise"
        hide-details
        clearable
        label="Franchise"
        density="compact"
        variant="outlined"
        class="ma-1"
        :items="galleryFilterStore.filterFranchises"
        @update:model-value="nextTick(() => emitter?.emit('filter', null))"
      />
      <v-autocomplete
        v-model="selectedCollection"
        hide-details
        clearable
        label="Collection"
        density="compact"
        variant="outlined"
        class="ma-1"
        :items="galleryFilterStore.filterCollections"
        @update:model-value="nextTick(() => emitter?.emit('filter', null))"
      />
      <v-autocomplete
        v-model="selectedCompany"
        hide-details
        clearable
        label="Company"
        density="compact"
        variant="outlined"
        class="ma-1"
        :items="galleryFilterStore.filterCompanies"
        @update:model-value="nextTick(() => emitter?.emit('filter', null))"
      />
    </v-row>
  </v-app-bar>
</template>
