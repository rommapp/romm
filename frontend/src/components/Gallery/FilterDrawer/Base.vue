<script setup lang="ts">
import FilterUnmatchedBtn from "@/components/Gallery/FilterDrawer/FilterUnmatchedBtn.vue";
import storeGalleryFilter from "@/stores/galleryFilter";
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import { inject, nextTick, ref } from "vue";

// Props
const showFilterBar = ref(false);
const emitter = inject<Emitter<Events>>("emitter");
emitter?.on("filterDrawerShow", () => {
  showFilterBar.value = !showFilterBar.value;
});

const galleryFilterStore = storeGalleryFilter();
const {
  selectedGenre,
  filterGenres,
  selectedFranchise,
  filterFranchises,
  selectedCollection,
  filterCollections,
  selectedCompany,
  filterCompanies,
} = storeToRefs(galleryFilterStore);

const filters = [
  {
    label: "Genre",
    selected: selectedGenre,
    items: filterGenres,
  },
  {
    label: "Franchise",
    selected: selectedFranchise,
    items: filterFranchises,
  },
  {
    label: "Collection",
    selected: selectedCollection,
    items: filterCollections,
  },
  {
    label: "Company",
    selected: selectedCompany,
    items: filterCompanies,
  },
];

// Functions
function resetFilters() {
  selectedGenre.value = null;
  selectedFranchise.value = null;
  selectedCollection.value = null;
  selectedCompany.value = null;
  galleryFilterStore.disableFilterUnmatched();
  nextTick(() => emitter?.emit("filter", null));
}
</script>

<template>
  <v-navigation-drawer
    @update:model-value="galleryFilterStore.switchActiveFilterDrawer()"
    floating
    v-model="showFilterBar"
    :mobile="true"
  >
    <v-list-item class="px-3 my-2">
      <filter-unmatched-btn />
    </v-list-item>
    <v-list-item v-for="filter in filters" class="pa-2">
      <v-autocomplete
        v-model="filter.selected.value"
        hide-details
        clearable
        :label="filter.label"
        density="compact"
        variant="outlined"
        class="ma-1"
        :items="filter.items.value"
        @update:model-value="nextTick(() => emitter?.emit('filter', null))"
      />
    </v-list-item>
    <v-list-item class="justify-center d-flex">
      <v-btn size="small" variant="tonal" @click="resetFilters">
        Reset filters</v-btn
      >
    </v-list-item>
  </v-navigation-drawer>
</template>
