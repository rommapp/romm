<script setup lang="ts">
import { debounce } from "lodash";
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import { inject, nextTick, onMounted, watch } from "vue";
import { useI18n } from "vue-i18n";
import { useRouter } from "vue-router";
import { useDisplay } from "vuetify";
import SearchTextField from "@/components/Gallery/AppBar/Search/SearchTextField.vue";
import FilterDuplicatesBtn from "@/components/Gallery/AppBar/common/FilterDrawer/FilterDuplicatesBtn.vue";
import FilterFavoritesBtn from "@/components/Gallery/AppBar/common/FilterDrawer/FilterFavoritesBtn.vue";
import FilterMatchedBtn from "@/components/Gallery/AppBar/common/FilterDrawer/FilterMatchedBtn.vue";
import FilterMissingBtn from "@/components/Gallery/AppBar/common/FilterDrawer/FilterMissingBtn.vue";
import FilterPlayablesBtn from "@/components/Gallery/AppBar/common/FilterDrawer/FilterPlayablesBtn.vue";
import FilterRaBtn from "@/components/Gallery/AppBar/common/FilterDrawer/FilterRaBtn.vue";
import FilterUnmatchedBtn from "@/components/Gallery/AppBar/common/FilterDrawer/FilterUnmatchedBtn.vue";
import FilterVerifiedBtn from "@/components/Gallery/AppBar/common/FilterDrawer/FilterVerifiedBtn.vue";
import MissingFromFSIcon from "@/components/common/MissingFromFSIcon.vue";
import PlatformIcon from "@/components/common/Platform/PlatformIcon.vue";
import storeGalleryFilter from "@/stores/galleryFilter";
import storePlatforms from "@/stores/platforms";
import storeRoms from "@/stores/roms";
import type { Events } from "@/types/emitter";

withDefaults(
  defineProps<{
    showPlayablesFilter?: boolean;
    showPlatformsFilter?: boolean;
    showSearchBar?: boolean;
  }>(),
  {
    showPlayablesFilter: true,
    showPlatformsFilter: false,
    showSearchBar: false,
  },
);

const { t } = useI18n();
const { xs, smAndDown } = useDisplay();
const router = useRouter();
const galleryFilterStore = storeGalleryFilter();
const romsStore = storeRoms();
const platformsStore = storePlatforms();
const {
  searchTerm,
  activeFilterDrawer,
  filterUnmatched,
  filterMatched,
  filterFavorites,
  filterDuplicates,
  filterPlayables,
  filterRA,
  filterMissing,
  filterVerified,
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

const onFilterChange = debounce(
  () => {
    romsStore.resetPagination();
    romsStore.fetchRoms({ galleryFilter: galleryFilterStore, concat: false });

    const url = new URL(window.location.href);
    // Update URL with filters
    Object.entries({
      search: searchTerm.value,
      filterMatched: filterMatched.value ? "1" : null,
      filterUnmatched: filterUnmatched.value ? "1" : null,
      filterFavorites: filterFavorites.value ? "1" : null,
      filterDuplicates: filterDuplicates.value ? "1" : null,
      filterPlayables: filterPlayables.value ? "1" : null,
      filterMissing: filterMissing.value ? "1" : null,
      filterVerified: filterVerified.value ? "1" : null,
      filterRA: filterRA.value ? "1" : null,
      platform: selectedPlatform.value
        ? String(selectedPlatform.value.id)
        : null,
      genre: selectedGenre.value,
      franchise: selectedFranchise.value,
      collection: selectedCollection.value,
      company: selectedCompany.value,
      ageRating: selectedAgeRating.value,
      region: selectedRegion.value,
      language: selectedLanguage.value,
      status: selectedStatus.value,
    }).forEach(([key, value]) => {
      if (value) {
        url.searchParams.set(key, value);
      } else {
        url.searchParams.delete(key);
      }
    });
    router.replace({ query: Object.fromEntries(url.searchParams.entries()) });
  },
  500,
  // If leading and trailing options are true, this is invoked on the trailing edge of
  // the timeout only if the the function is invoked more than once during the wait
  { leading: false, trailing: true },
);

emitter?.on("filterRoms", onFilterChange);

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

function resetFilters() {
  galleryFilterStore.resetFilters();
  nextTick(() => emitter?.emit("filterRoms", null));
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
  const {
    search: urlSearch,
    filterMatched: urlFilteredMatch,
    filterUnmatched: urlFilteredUnmatched,
    filterFavorites: urlFilteredFavorites,
    filterDuplicates: urlFilteredDuplicates,
    filterPlayables: urlFilteredPlayables,
    filterMissing: urlFilteredMissing,
    filterVerified: urlFilteredVerified,
    filterRA: urlFilteredRa,
    platform: urlPlatform,
    genre: urlGenre,
    franchise: urlFranchise,
    collection: urlCollection,
    company: urlCompany,
    ageRating: urlAgeRating,
    region: urlRegion,
    language: urlLanguage,
    status: urlStatus,
  } = router.currentRoute.value.query;

  // Check for query params to set filters
  if (urlFilteredMatch !== undefined) {
    galleryFilterStore.setFilterMatched(true);
  }
  if (urlFilteredUnmatched !== undefined) {
    galleryFilterStore.setFilterUnmatched(true);
  }
  if (urlFilteredFavorites !== undefined) {
    galleryFilterStore.setFilterFavorites(true);
  }
  if (urlFilteredDuplicates !== undefined) {
    galleryFilterStore.setFilterDuplicates(true);
  }
  if (urlFilteredPlayables !== undefined) {
    galleryFilterStore.setFilterPlayables(true);
  }
  if (urlFilteredMissing !== undefined) {
    galleryFilterStore.setFilterMissing(true);
  }
  if (urlFilteredVerified !== undefined) {
    galleryFilterStore.setFilterVerified(true);
  }
  if (urlFilteredRa !== undefined) {
    galleryFilterStore.setFilterRA(true);
  }
  if (urlPlatform !== undefined) {
    const platform = platformsStore.get(Number(urlPlatform));
    if (platform) galleryFilterStore.setSelectedFilterPlatform(platform);
  }
  if (urlGenre !== undefined) {
    galleryFilterStore.setSelectedFilterGenre(urlGenre as string);
  }
  if (urlFranchise !== undefined) {
    galleryFilterStore.setSelectedFilterFranchise(urlFranchise as string);
  }
  if (urlCollection !== undefined) {
    galleryFilterStore.setSelectedFilterCollection(urlCollection as string);
  }
  if (urlCompany !== undefined) {
    galleryFilterStore.setSelectedFilterCompany(urlCompany as string);
  }
  if (urlAgeRating !== undefined) {
    galleryFilterStore.setSelectedFilterAgeRating(urlAgeRating as string);
  }
  if (urlRegion !== undefined) {
    galleryFilterStore.setSelectedFilterRegion(urlRegion as string);
  }
  if (urlLanguage !== undefined) {
    galleryFilterStore.setSelectedFilterLanguage(urlLanguage as string);
  }
  if (urlStatus !== undefined) {
    galleryFilterStore.setSelectedFilterStatus(urlStatus as string);
  }

  // Check if search term is set in the URL (empty string is ok)
  const freshSearch = urlSearch !== undefined && urlSearch !== searchTerm.value;
  if (freshSearch) {
    searchTerm.value = urlSearch as string;
    romsStore.resetPagination();
  }

  // Fire off search if URL state prepopulated
  if (freshSearch || galleryFilterStore.isFiltered()) {
    emitter?.emit("filterRoms", null);
  }

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
    v-model="activeFilterDrawer"
    mobile
    floating
    width="400"
    :class="{
      'ml-2': activeFilterDrawer,
      'drawer-mobile': smAndDown && activeFilterDrawer,
    }"
    class="bg-surface rounded mt-4 mb-2 pa-1 unset-height"
  >
    <v-list tabindex="-1">
      <template v-if="showSearchBar && xs">
        <v-list-item>
          <SearchTextField :tabindex="activeFilterDrawer ? 0 : -1" />
        </v-list-item>
      </template>
      <v-list-item>
        <FilterUnmatchedBtn :tabindex="activeFilterDrawer ? 0 : -1" />
        <FilterMatchedBtn
          class="mt-2"
          :tabindex="activeFilterDrawer ? 0 : -1"
        />
        <FilterFavoritesBtn
          class="mt-2"
          :tabindex="activeFilterDrawer ? 0 : -1"
        />
        <FilterDuplicatesBtn
          class="mt-2"
          :tabindex="activeFilterDrawer ? 0 : -1"
        />
        <FilterPlayablesBtn
          v-if="showPlayablesFilter"
          class="mt-2"
          :tabindex="activeFilterDrawer ? 0 : -1"
        />
        <FilterMissingBtn
          class="mt-2"
          :tabindex="activeFilterDrawer ? 0 : -1"
        />
        <FilterVerifiedBtn
          class="mt-2"
          :tabindex="activeFilterDrawer ? 0 : -1"
        />
        <FilterRaBtn class="mt-2" :tabindex="activeFilterDrawer ? 0 : -1" />
      </v-list-item>
      <v-list-item
        v-if="showPlatformsFilter"
        :tabindex="activeFilterDrawer ? 0 : -1"
      >
        <v-autocomplete
          v-model="selectedPlatform"
          :tabindex="activeFilterDrawer ? 0 : -1"
          hide-details
          prepend-inner-icon="mdi-controller"
          clearable
          :label="t('common.platform')"
          variant="outlined"
          density="comfortable"
          :items="filterPlatforms"
          @update:model-value="
            nextTick(() => emitter?.emit('filterRoms', null))
          "
        >
          <template #item="{ props, item }">
            <v-list-item
              v-bind="props"
              class="py-4"
              :title="item.raw.name ?? ''"
              :subtitle="item.raw.fs_slug"
            >
              <template #prepend>
                <PlatformIcon
                  :key="item.raw.slug"
                  :size="35"
                  :slug="item.raw.slug"
                  :name="item.raw.name"
                  :fs-slug="item.raw.fs_slug"
                />
              </template>
              <template #append>
                <MissingFromFSIcon
                  v-if="item.raw.missing_from_fs"
                  text="Missing platform from filesystem"
                  chip
                  chip-label
                  chip-density="compact"
                  class="ml-2"
                />
                <v-chip class="ml-2" size="x-small" label>
                  {{ item.raw.rom_count }}
                </v-chip>
              </template>
            </v-list-item>
          </template>
          <template #chip="{ item }">
            <v-chip>
              <PlatformIcon
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
      <v-list-item
        v-for="filter in filters"
        :key="filter.label"
        :tabindex="activeFilterDrawer ? 0 : -1"
      >
        <v-autocomplete
          v-model="filter.selected.value"
          :tabindex="activeFilterDrawer ? 0 : -1"
          hide-details
          clearable
          :label="filter.label"
          variant="solo-filled"
          density="comfortable"
          :items="filter.items.value"
          @update:model-value="
            nextTick(() => emitter?.emit('filterRoms', null))
          "
        />
      </v-list-item>
      <v-list-item
        class="justify-center d-flex"
        :tabindex="activeFilterDrawer ? 0 : -1"
      >
        <v-btn
          :tabindex="activeFilterDrawer ? 0 : -1"
          size="small"
          variant="tonal"
          @click="resetFilters"
        >
          {{ t("platform.reset-filters") }}
        </v-btn>
      </v-list-item>
    </v-list>
  </v-navigation-drawer>
</template>
