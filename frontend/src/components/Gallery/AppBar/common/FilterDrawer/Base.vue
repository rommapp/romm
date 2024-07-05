<script setup lang="ts">
import FilterUnmatchedBtn from "@/components/Gallery/AppBar/common/FilterDrawer/FilterUnmatchedBtn.vue";
import FilterFavouritesBtn from "@/components/Gallery/AppBar/common/FilterDrawer/FilterFavouritesBtn.vue";
import storeGalleryFilter from "@/stores/galleryFilter";
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import { inject, nextTick, ref } from "vue";

// Props
const show = ref(false);
const emitter = inject<Emitter<Events>>("emitter");
const galleryFilterStore = storeGalleryFilter();
const {
  activeFilterDrawer,
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
  galleryFilterStore.disableFilterFavourites();
  nextTick(() => emitter?.emit("filter", null));
}
</script>

<template>
  <v-navigation-drawer
    @update:model-value="galleryFilterStore.switchActiveFilterDrawer()"
    floating
    width="300"
    v-model="activeFilterDrawer"
    mobile
  >
    <v-list>
      <v-list-item>
        <filter-unmatched-btn />
        <filter-favourites-btn class="mt-2" />
      </v-list-item>
      <v-list-item v-for="filter in filters">
        <v-autocomplete
          rounded="0"
          v-model="filter.selected.value"
          hide-details
          clearable
          :label="filter.label"
          variant="solo-filled"
          density="comfortable"
          :items="filter.items.value"
          @update:model-value="nextTick(() => emitter?.emit('filter', null))"
        />
      </v-list-item>
      <v-list-item class="justify-center d-flex">
        <v-btn size="small" variant="tonal" @click="resetFilters">
          Reset filters</v-btn
        >
      </v-list-item>
    </v-list>
  </v-navigation-drawer>
</template>
