<script setup lang="ts">
import storeRoms from "@/stores/roms";
import storeGalleryFilter, { type FilterType } from "@/stores/galleryFilter";
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { inject, nextTick, onMounted, watch } from "vue";
import { storeToRefs } from "pinia";
import { useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import { debounce } from "lodash";

// Props
const { t } = useI18n();
const router = useRouter();
const romsStore = storeRoms();
const { initialSearch } = storeToRefs(romsStore);
const emitter = inject<Emitter<Events>>("emitter");
const galleryFilterStore = storeGalleryFilter();
const { searchTerm } = storeToRefs(galleryFilterStore);

async function fetchRoms() {
  if (searchTerm.value === null) return;

  initialSearch.value = true;
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

const refetchRoms = debounce(async () => {
  if (searchTerm.value === null) return;

  // Update URL with search term
  router.replace({ query: { search: searchTerm.value } });

  romsStore.resetPagination();
  initialSearch.value = true;
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
}, 500);

function clearInput() {
  searchTerm.value = null;
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

  // Check if search term is set in the URL (empty string is ok)
  if (searchTerm.value !== null) {
    fetchRoms();
  }
});

watch(
  () => router.currentRoute.value.query,
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
    density="default"
    clearable
    autofocus
    hide-details
    rounded="0"
    :label="t('common.search')"
    v-model="searchTerm"
    @keyup.enter="refetchRoms"
    @click:clear="clearInput"
    @update:model-value="nextTick(refetchRoms)"
  />
</template>
