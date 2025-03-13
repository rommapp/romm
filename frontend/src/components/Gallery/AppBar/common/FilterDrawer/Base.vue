<script setup lang="ts">
import FilterUnmatchedBtn from "@/components/Gallery/AppBar/common/FilterDrawer/FilterUnmatchedBtn.vue";
import FilterMatchedBtn from "@/components/Gallery/AppBar/common/FilterDrawer/FilterMatchedBtn.vue";
import FilterFavouritesBtn from "@/components/Gallery/AppBar/common/FilterDrawer/FilterFavouritesBtn.vue";
import FilterDuplicatesBtn from "@/components/Gallery/AppBar/common/FilterDrawer/FilterDuplicatesBtn.vue";
import FilterTextField from "@/components/Gallery/AppBar/common/FilterTextField.vue";
import SearchTextField from "@/components/Gallery/AppBar/Search/SearchTextField.vue";
import SearchBtn from "@/components/Gallery/AppBar/Search/SearchBtn.vue";
import storeGalleryFilter from "@/stores/galleryFilter";
import storeRoms from "@/stores/roms";
import storePlatforms from "@/stores/platforms";
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import { inject, nextTick, onMounted, ref, watch } from "vue";
import { useDisplay } from "vuetify";
import { useI18n } from "vue-i18n";

// Props
withDefaults(defineProps<{ hidePlatforms?: boolean }>(), {
  hidePlatforms: false,
});

const { t } = useI18n();
const { xs, smAndDown } = useDisplay();
const viewportWidth = ref(window.innerWidth);
const galleryFilterStore = storeGalleryFilter();
const romsStore = storeRoms();
const platformsStore = storePlatforms();
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
  selectedAgeRating,
  filterAgeRatings,
  selectedStatus,
  filterStatuses,
  selectedPlatform,
  filterPlatforms,
} = storeToRefs(galleryFilterStore);
const { allRoms, filteredRoms } = storeToRefs(romsStore);
const { allPlatforms } = storeToRefs(platformsStore);
const emitter = inject<Emitter<Events>>("emitter");
emitter?.on("filter", onFilterChange);

async function onFilterChange() {
  romsStore.setFiltered(allRoms.value, galleryFilterStore);
  emitter?.emit("updateDataTablePages", null);
}

const filters = [
  {
    label: t("platform.genre"),
    selected: selectedGenre,
    items: filterGenres,
  },
  {
    label: t("platform.franchise"),
    selected: selectedFranchise,
    items: filterFranchises,
  },
  {
    label: t("platform.collection"),
    selected: selectedCollection,
    items: filterCollections,
  },
  {
    label: t("platform.company"),
    selected: selectedCompany,
    items: filterCompanies,
  },
  {
    label: t("platform.age-rating"),
    selected: selectedAgeRating,
    items: filterAgeRatings,
  },
  {
    label: t("platform.status"),
    selected: selectedStatus,
    items: filterStatuses,
  },
];

// Functions
function resetFilters() {
  selectedPlatform.value = null;
  selectedGenre.value = null;
  selectedFranchise.value = null;
  selectedCollection.value = null;
  selectedCompany.value = null;
  selectedAgeRating.value = null;
  selectedStatus.value = null;
  galleryFilterStore.disableFilterUnmatched();
  galleryFilterStore.disableFilterMatched();
  galleryFilterStore.disableFilterFavourites();
  nextTick(() => emitter?.emit("filter", null));
}

function setFilters() {
  galleryFilterStore.setFilterPlatforms([
    ...new Set(
      romsStore.filteredRoms
        .flatMap((rom) => platformsStore.get(rom.platform_id))
        .filter((platform) => !!platform)
        .sort(),
    ),
  ]);
  galleryFilterStore.setFilterGenres([
    ...new Set(
      romsStore.filteredRoms
        .flatMap((rom) => rom.genres.map((genre) => genre))
        .sort(),
    ),
  ]);
  galleryFilterStore.setFilterFranchises([
    ...new Set(
      romsStore.filteredRoms
        .flatMap((rom) => rom.franchises.map((franchise) => franchise))
        .sort(),
    ),
  ]);
  galleryFilterStore.setFilterCompanies([
    ...new Set(
      romsStore.filteredRoms
        .flatMap((rom) => rom.companies.map((company) => company))
        .sort(),
    ),
  ]);
  galleryFilterStore.setFilterCollections([
    ...new Set(
      romsStore.filteredRoms
        .flatMap((rom) => rom.meta_collections.map((collection) => collection))
        .sort(),
    ),
  ]);
  galleryFilterStore.setFilterAgeRatings([
    ...new Set(
      romsStore.filteredRoms
        .flatMap((rom) => rom.age_ratings.map((ageRating) => ageRating))
        .sort(),
    ),
  ]);
}

onMounted(async () => {
  watch(
    () => filteredRoms.value,
    async () => setFilters(),
    { immediate: true }, // Ensure watcher is triggered immediately
  );

  watch(
    () => allPlatforms.value,
    async () => setFilters(),
    { immediate: true }, // Ensure watcher is triggered immediately
  );
});
</script>

<template>
  <v-navigation-drawer
    mobile
    floating
    :width="xs ? viewportWidth : '350'"
    v-model="activeFilterDrawer"
    @update:model-value="galleryFilterStore.switchActiveFilterDrawer()"
    :class="{
      'mx-2 px-1': activeFilterDrawer,
      'drawer-mobile': smAndDown && activeFilterDrawer,
      'drawer-desktop': !smAndDown,
    }"
    class="bg-surface border-0 rounded my-2 py-1"
    style="height: unset"
  >
    <v-list>
      <template v-if="xs">
        <template v-if="$route.name != 'search'">
          <v-list-item>
            <filter-text-field />
          </v-list-item>
        </template>
        <template v-if="$route.name == 'search'">
          <v-list-item>
            <v-row no-gutters>
              <v-col>
                <search-text-field />
              </v-col>
              <v-col cols="auto">
                <search-btn />
              </v-col>
            </v-row>
          </v-list-item>
        </template>
      </template>
      <v-list-item>
        <filter-unmatched-btn />
        <filter-matched-btn class="mt-2" />
        <filter-favourites-btn class="mt-2" />
        <filter-duplicates-btn class="mt-2" />
      </v-list-item>
      <v-list-item v-if="!hidePlatforms">
        <v-autocomplete
          v-model="selectedPlatform"
          hide-details
          clearable
          :label="t('common.platform')"
          variant="solo-filled"
          density="comfortable"
          :items="filterPlatforms.map((p) => ({ title: p.name, value: p }))"
          @update:model-value="nextTick(() => emitter?.emit('filter', null))"
        />
      </v-list-item>
      <v-list-item v-for="filter in filters">
        <v-autocomplete
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
          {{ t("platform.reset-filters") }}
        </v-btn>
      </v-list-item>
    </v-list>
  </v-navigation-drawer>
</template>
<style scoped>
.drawer-desktop {
  top: 56px !important;
}
.drawer-mobile {
  top: 110px !important;
  width: calc(100% - 16px) !important;
}
</style>
