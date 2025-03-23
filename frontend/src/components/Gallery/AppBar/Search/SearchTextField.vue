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
const { fetchingRoms } = storeToRefs(romsStore);
const emitter = inject<Emitter<Events>>("emitter");
const galleryFilterStore = storeGalleryFilter();
const { searchTerm } = storeToRefs(galleryFilterStore);

async function fetchRoms() {
  if (searchTerm.value === null) return;

  romsStore
    .fetchRoms(galleryFilterStore)
    .catch((error) => {
      emitter?.emit("snackbarShow", {
        msg: `Couldn't fetch roms: ${error}`,
        icon: "mdi-close-circle",
        color: "red",
        timeout: 4000,
      });
    })
    .finally(() => {
      galleryFilterStore.activeFilterDrawer = false;
    });
}

async function refetchRoms() {
  if (searchTerm.value === null) return;

  // Auto hide android keyboard
  const inputElement = document.getElementById("search-text-field");
  inputElement?.blur();

  // Update URL with search term
  router.replace({ query: { search: searchTerm.value } });

  romsStore.resetPagination();
  romsStore
    .fetchRoms(galleryFilterStore, false)
    .catch((error) => {
      emitter?.emit("snackbarShow", {
        msg: `Couldn't fetch roms: ${error}`,
        icon: "mdi-close-circle",
        color: "red",
        timeout: 4000,
      });
    })
    .finally(() => {
      galleryFilterStore.activeFilterDrawer = false;
    });
}

const filterToSetFilter: Record<FilterType, Function> = {
  genres: galleryFilterStore.setSelectedFilterGenre,
  franchises: galleryFilterStore.setSelectedFilterFranchise,
  collections: galleryFilterStore.setSelectedFilterCollection,
  companies: galleryFilterStore.setSelectedFilterCompany,
  age_ratings: galleryFilterStore.setSelectedFilterAgeRating,
  status: galleryFilterStore.setSelectedFilterStatus,
  regions: galleryFilterStore.setSelectedFilterRegion,
  languages: galleryFilterStore.setSelectedFilterLanguage,
};

onMounted(() => {
  const {
    search: searchParam,
    filter: filterParam,
    value: valueParam,
  } = router.currentRoute.value.query;
  if (searchParam !== undefined && searchParam !== searchTerm.value) {
    searchTerm.value = searchParam as string;
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
    if (query.search !== undefined && query.search !== searchTerm.value) {
      searchTerm.value = query.search as string;
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
    @keyup.enter="refetchRoms"
    v-model="searchTerm"
    :disabled="fetchingRoms"
    :label="t('common.search')"
    hide-details
    class="bg-toplayer"
  />
</template>
