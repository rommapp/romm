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
    <v-row
      no-gutters
      class="pa-1"
    >
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
    <v-divider
      :thickness="2"
      class="mx-2 border-opacity-25"
      color="romm-accent-1"
    />
  </div>
</template>
