<script setup lang="ts">
import romApi from "@/services/api/rom";
import storeRoms from "@/stores/roms";
import storeGalleryFilter, { type FilterType } from "@/stores/galleryFilter";
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { inject, onMounted, watch } from "vue";
import { storeToRefs } from "pinia";
import { useDisplay } from "vuetify";
import { useRouter } from "vue-router";
import { useI18n } from "vue-i18n";

// Props
const { xs } = useDisplay();
const { t } = useI18n();
const router = useRouter();
const romsStore = storeRoms();
const { gettingRoms } = storeToRefs(romsStore);
const emitter = inject<Emitter<Events>>("emitter");
const galleryFilterStore = storeGalleryFilter();
const { searchText } = storeToRefs(galleryFilterStore);

async function fetchRoms() {
  if (searchText.value !== null) {
    // Auto hide android keyboard
    const inputElement = document.getElementById("search-text-field");
    inputElement?.blur();
    gettingRoms.value = true;

    // Update URL with search term
    router.replace({ query: { search: searchText.value } });

    try {
      const { data } = await romApi.getRoms({ searchTerm: searchText.value });
      const sortedData = data.sort((a, b) => {
        return a.platform_name.localeCompare(b.platform_name);
      });
      romsStore.set(sortedData);
      romsStore.setFiltered(sortedData, galleryFilterStore);
    } catch (error) {
      emitter?.emit("snackbarShow", {
        msg: `Couldn't fetch roms: ${error}`,
        icon: "mdi-close-circle",
        color: "red",
        timeout: 4000,
      });
      console.error(`Couldn't fetch roms: ${error}`);
    } finally {
      gettingRoms.value = false;
      galleryFilterStore.activeFilterDrawer = false;
    }
  }
}

const filterToSetFilter: Record<FilterType, Function> = {
  genres: galleryFilterStore.setSelectedFilterGenre,
  franchises: galleryFilterStore.setSelectedFilterFranchise,
  meta_collections: galleryFilterStore.setSelectedFilterCollection,
  companies: galleryFilterStore.setSelectedFilterCompany,
  age_ratings: galleryFilterStore.setSelectedFilterAgeRating,
  status: galleryFilterStore.setSelectedFilterStatus,
};

onMounted(() => {
  const {
    search: searchParam,
    filter: filterParam,
    value: valueParam,
  } = router.currentRoute.value.query;
  if (searchParam !== undefined && searchParam !== searchText.value) {
    searchText.value = searchParam as string;
  }

  // Check for query params to set filters
  if (filterParam && valueParam) {
    const filter = filterParam as FilterType;
    const value = valueParam as string;
    filterToSetFilter[filter](value);
    emitter?.emit("filter", null);
    router.replace({ query: {} }); // Clear query params
  }

  fetchRoms();
});

watch(
  router.currentRoute.value.query,
  (query) => {
    if (query.search !== undefined && query.search !== searchText.value) {
      searchText.value = query.search as string;
      fetchRoms();
    }
  },
  { deep: true },
);
</script>

<template>
  <v-text-field
    :density="xs ? 'comfortable' : 'default'"
    clearable
    autofocus
    @keyup.enter="fetchRoms"
    v-model="searchText"
    :disabled="gettingRoms"
    :label="t('common.search')"
    hide-details
    class="bg-toplayer"
  />
</template>
