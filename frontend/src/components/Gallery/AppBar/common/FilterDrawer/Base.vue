<script setup lang="ts">
import PlatformIcon from "@/components/common/Platform/Icon.vue";
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
withDefaults(
  defineProps<{
    showPlatformsFilter?: boolean;
    showFilterBar?: boolean;
    showSearchBar?: boolean;
  }>(),
  {
    showPlatformsFilter: false,
    showFilterBar: false,
    showSearchBar: false,
  },
);

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
  selectedRegion,
  filterRegions,
  selectedLanguage,
  filterLanguages,
} = storeToRefs(galleryFilterStore);
const { filteredRoms } = storeToRefs(romsStore);
const { allPlatforms } = storeToRefs(platformsStore);
const emitter = inject<Emitter<Events>>("emitter");
emitter?.on("filter", onFilterChange);

async function onFilterChange() {
  romsStore.resetPagination();
  romsStore.fetchRoms(galleryFilterStore, false);
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
    label: t("platform.region"),
    selected: selectedRegion,
    items: filterRegions,
  },
  {
    label: t("platform.language"),
    selected: selectedLanguage,
    items: filterLanguages,
  },
  {
    label: t("platform.status"),
    selected: selectedStatus,
    items: filterStatuses,
  },
];

// Functions
function resetFilters() {
  galleryFilterStore.resetFilters();
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
      romsStore.filteredRoms.flatMap((rom) => rom.metadatum.genres).sort(),
    ),
  ]);
  galleryFilterStore.setFilterFranchises([
    ...new Set(
      romsStore.filteredRoms.flatMap((rom) => rom.metadatum.franchises).sort(),
    ),
  ]);
  galleryFilterStore.setFilterCompanies([
    ...new Set(
      romsStore.filteredRoms.flatMap((rom) => rom.metadatum.companies).sort(),
    ),
  ]);
  galleryFilterStore.setFilterCollections([
    ...new Set(
      romsStore.filteredRoms.flatMap((rom) => rom.metadatum.collections).sort(),
    ),
  ]);
  galleryFilterStore.setFilterAgeRatings([
    ...new Set(
      romsStore.filteredRoms.flatMap((rom) => rom.metadatum.age_ratings).sort(),
    ),
  ]);
  galleryFilterStore.setFilterRegions([
    ...new Set(romsStore.filteredRoms.flatMap((rom) => rom.regions).sort()),
  ]);
  galleryFilterStore.setFilterLanguages([
    ...new Set(romsStore.filteredRoms.flatMap((rom) => rom.languages).sort()),
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
    width="500"
    v-model="activeFilterDrawer"
    @update:model-value="galleryFilterStore.switchActiveFilterDrawer()"
    :class="{
      'ml-2': activeFilterDrawer,
      'drawer-mobile': smAndDown && activeFilterDrawer,
    }"
    class="bg-surface rounded mt-4 mb-2 pa-1 unset-height"
  >
    <v-list>
      <template v-if="showFilterBar && xs">
        <v-list-item>
          <filter-text-field />
        </v-list-item>
      </template>
      <template v-if="showSearchBar && xs">
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
      <v-list-item>
        <filter-unmatched-btn />
        <filter-matched-btn class="mt-2" />
        <filter-favourites-btn class="mt-2" />
        <filter-duplicates-btn class="mt-2" />
      </v-list-item>
      <v-list-item v-if="showPlatformsFilter">
        <v-autocomplete
          v-model="selectedPlatform"
          hide-details
          prepend-inner-icon="mdi-controller"
          clearable
          :label="t('common.platform')"
          variant="outlined"
          density="comfortable"
          class="my-2"
          :items="filterPlatforms"
          @update:model-value="nextTick(() => emitter?.emit('filter', null))"
        >
          <template #item="{ props, item }">
            <v-list-item
              v-bind="props"
              class="py-4"
              :title="item.raw.name ?? ''"
              :subtitle="item.raw.fs_slug"
            >
              <template #prepend>
                <platform-icon
                  :key="item.raw.slug"
                  :size="35"
                  :slug="item.raw.slug"
                  :name="item.raw.name"
                  :fs-slug="item.raw.fs_slug"
                />
              </template>
              <template #append>
                <v-chip class="ml-2" size="x-small" label>
                  {{ item.raw.rom_count }}
                </v-chip>
              </template>
            </v-list-item>
          </template>
          <template #chip="{ item }">
            <v-chip>
              <platform-icon
                :key="item.raw.slug"
                :slug="item.raw.slug"
                :name="item.raw.name"
                :fs-slug="item.raw.fs_slug"
                :size="20"
                class="mr-2"
              />
              {{ item.raw.name }}
            </v-chip>
          </template>
        </v-autocomplete>
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
