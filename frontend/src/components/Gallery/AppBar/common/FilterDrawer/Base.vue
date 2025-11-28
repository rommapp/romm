<script setup lang="ts">
import { debounce } from "lodash";
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import { inject, nextTick, onMounted, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import { useRouter } from "vue-router";
import { useDisplay } from "vuetify";
import SearchTextField from "@/components/Gallery/AppBar/Search/SearchTextField.vue";
import FilterDuplicatesBtn from "@/components/Gallery/AppBar/common/FilterDrawer/FilterDuplicatesBtn.vue";
import FilterFavoritesBtn from "@/components/Gallery/AppBar/common/FilterDrawer/FilterFavoritesBtn.vue";
import FilterMatchStateBtn from "@/components/Gallery/AppBar/common/FilterDrawer/FilterMatchStateBtn.vue";
import FilterMissingBtn from "@/components/Gallery/AppBar/common/FilterDrawer/FilterMissingBtn.vue";
import FilterPlatformBtn from "@/components/Gallery/AppBar/common/FilterDrawer/FilterPlatformBtn.vue";
import FilterPlayablesBtn from "@/components/Gallery/AppBar/common/FilterDrawer/FilterPlayablesBtn.vue";
import FilterRaBtn from "@/components/Gallery/AppBar/common/FilterDrawer/FilterRaBtn.vue";
import FilterVerifiedBtn from "@/components/Gallery/AppBar/common/FilterDrawer/FilterVerifiedBtn.vue";
import cachedApiService from "@/services/cache/api";
import storeGalleryFilter from "@/stores/galleryFilter";
import storePlatforms from "@/stores/platforms";
import storeRoms, { type SimpleRom } from "@/stores/roms";
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
  selectedGenres,
  genresLogic,
  selectedFranchise,
  filterFranchises,
  selectedFranchises,
  franchisesLogic,
  selectedCollection,
  filterCollections,
  selectedCollections,
  collectionsLogic,
  selectedCompany,
  filterCompanies,
  selectedCompanies,
  companiesLogic,
  selectedAgeRating,
  filterAgeRatings,
  selectedAgeRatings,
  ageRatingsLogic,
  selectedStatus,
  filterStatuses,
  selectedStatuses,
  statusesLogic,
  selectedPlatforms,
  selectedRegion,
  filterRegions,
  selectedRegions,
  regionsLogic,
  selectedLanguage,
  filterLanguages,
  selectedLanguages,
  languagesLogic,
} = storeToRefs(galleryFilterStore);
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
      matched:
        filterMatched.value === true
          ? "1"
          : filterUnmatched.value === true
            ? "2"
            : null,
      filterFavorites:
        filterFavorites.value === true
          ? "1"
          : filterFavorites.value === false
            ? "0"
            : null,
      filterDuplicates:
        filterDuplicates.value === true
          ? "1"
          : filterDuplicates.value === false
            ? "0"
            : null,
      filterPlayables:
        filterPlayables.value === true
          ? "1"
          : filterPlayables.value === false
            ? "0"
            : null,
      filterMissing:
        filterMissing.value === true
          ? "1"
          : filterMissing.value === false
            ? "0"
            : null,
      filterVerified:
        filterVerified.value === true
          ? "1"
          : filterVerified.value === false
            ? "0"
            : null,
      filterRA:
        filterRA.value === true ? "1" : filterRA.value === false ? "0" : null,
      platforms:
        selectedPlatforms.value.length > 0
          ? selectedPlatforms.value.map((p) => String(p.id)).join(",")
          : null,
      genre: selectedGenre.value,
      genres:
        selectedGenres.value.length > 0 ? selectedGenres.value.join(",") : null,
      genresLogic: selectedGenres.value.length > 1 ? genresLogic.value : null,
      franchise: selectedFranchise.value,
      franchises:
        selectedFranchises.value.length > 0
          ? selectedFranchises.value.join(",")
          : null,
      franchisesLogic:
        selectedFranchises.value.length > 1 ? franchisesLogic.value : null,
      collection: selectedCollection.value,
      collections:
        selectedCollections.value.length > 0
          ? selectedCollections.value.join(",")
          : null,
      collectionsLogic:
        selectedCollections.value.length > 1 ? collectionsLogic.value : null,
      company: selectedCompany.value,
      companies:
        selectedCompanies.value.length > 0
          ? selectedCompanies.value.join(",")
          : null,
      companiesLogic:
        selectedCompanies.value.length > 1 ? companiesLogic.value : null,
      ageRating: selectedAgeRating.value,
      ageRatings:
        selectedAgeRatings.value.length > 0
          ? selectedAgeRatings.value.join(",")
          : null,
      ageRatingsLogic:
        selectedAgeRatings.value.length > 1 ? ageRatingsLogic.value : null,
      region: selectedRegion.value,
      regions:
        selectedRegions.value.length > 0
          ? selectedRegions.value.join(",")
          : null,
      regionsLogic:
        selectedRegions.value.length > 1 ? regionsLogic.value : null,
      language: selectedLanguage.value,
      languages:
        selectedLanguages.value.length > 0
          ? selectedLanguages.value.join(",")
          : null,
      languagesLogic:
        selectedLanguages.value.length > 1 ? languagesLogic.value : null,
      status: selectedStatus.value,
      statuses:
        selectedStatuses.value.length > 0
          ? selectedStatuses.value.join(",")
          : null,
      statusesLogic:
        selectedStatuses.value.length > 1 ? statusesLogic.value : null,
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

// Separate debounced function for search term changes
const onSearchChange = debounce(
  async () => {
    await fetchSearchFilteredRoms();
    setFilters();
  },
  500,
  { leading: false, trailing: true },
);

emitter?.on("filterRoms", onFilterChange);

const filters = [
  {
    label: t("platform.genre"),
    selected: selectedGenres,
    items: filterGenres,
    logic: genresLogic,
    setLogic: (logic: "any" | "all") =>
      galleryFilterStore.setGenresLogic(logic),
  },
  {
    label: t("platform.franchise"),
    selected: selectedFranchises,
    items: filterFranchises,
    logic: franchisesLogic,
    setLogic: (logic: "any" | "all") =>
      galleryFilterStore.setFranchisesLogic(logic),
  },
  {
    label: t("platform.collection"),
    selected: selectedCollections,
    items: filterCollections,
    logic: collectionsLogic,
    setLogic: (logic: "any" | "all") =>
      galleryFilterStore.setCollectionsLogic(logic),
  },
  {
    label: t("platform.company"),
    selected: selectedCompanies,
    items: filterCompanies,
    logic: companiesLogic,
    setLogic: (logic: "any" | "all") =>
      galleryFilterStore.setCompaniesLogic(logic),
  },
  {
    label: t("platform.age-rating"),
    selected: selectedAgeRatings,
    items: filterAgeRatings,
    logic: ageRatingsLogic,
    setLogic: (logic: "any" | "all") =>
      galleryFilterStore.setAgeRatingsLogic(logic),
  },
  {
    label: t("platform.region"),
    selected: selectedRegions,
    items: filterRegions,
    logic: regionsLogic,
    setLogic: (logic: "any" | "all") =>
      galleryFilterStore.setRegionsLogic(logic),
  },
  {
    label: t("platform.language"),
    selected: selectedLanguages,
    items: filterLanguages,
    logic: languagesLogic,
    setLogic: (logic: "any" | "all") =>
      galleryFilterStore.setLanguagesLogic(logic),
  },
  {
    label: t("platform.status"),
    selected: selectedStatuses,
    items: filterStatuses,
    logic: statusesLogic,
    setLogic: (logic: "any" | "all") =>
      galleryFilterStore.setStatusesLogic(logic),
  },
];

function resetFilters() {
  galleryFilterStore.resetFilters();
  nextTick(async () => {
    await fetchSearchFilteredRoms();
    setFilters();
    emitter?.emit("filterRoms", null);
  });
}

// Store search-filtered ROMs for populating filter options
let searchFilteredRoms = ref<SimpleRom[]>([]);

async function fetchSearchFilteredRoms() {
  try {
    const params = {
      searchTerm: searchTerm.value,
      platformIds: romsStore.currentPlatform
        ? [romsStore.currentPlatform.id]
        : null,
      collectionId: romsStore.currentCollection?.id ?? null,
      virtualCollectionId: romsStore.currentVirtualCollection?.id ?? null,
      smartCollectionId: romsStore.currentSmartCollection?.id ?? null,
      limit: 10000, // Get enough ROMs to populate filters
      offset: 0,
      orderBy: romsStore.orderBy,
      orderDir: romsStore.orderDir,
      // Exclude all other filters
      filterUnmatched: false,
      filterMatched: false,
      filterFavorites: null,
      filterDuplicates: null,
      filterPlayables: null,
      filterRA: null,
      filterMissing: null,
      filterVerified: null,
      // Single value filters - exclude
      selectedGenre: null,
      selectedFranchise: null,
      selectedCollection: null,
      selectedCompany: null,
      selectedAgeRating: null,
      selectedRegion: null,
      selectedLanguage: null,
      selectedStatus: null,
      // Multi-value filters - exclude
      selectedGenres: null,
      selectedFranchises: null,
      selectedCollections: null,
      selectedCompanies: null,
      selectedAgeRatings: null,
      selectedRegions: null,
      selectedLanguages: null,
    };

    // Fetch ROMs with only search term applied (and current platform/collection context)
    const response = await cachedApiService.getRoms(params, () => {}); // No background update callback needed

    searchFilteredRoms.value = response.data.items;
  } catch (error) {
    console.error("Failed to fetch search-filtered ROMs:", error);
    // Fall back to current filtered ROMs if search-only fetch fails
    searchFilteredRoms.value = romsStore.filteredRoms;
  }
}

function setFilters() {
  const romsForFilters =
    searchFilteredRoms.value.length > 0
      ? searchFilteredRoms.value
      : romsStore.filteredRoms;

  galleryFilterStore.setFilterPlatforms([
    ...new Set(
      romsForFilters
        .flatMap((rom) => platformsStore.get(rom.platform_id))
        .filter((platform) => !!platform)
        .sort(),
    ),
  ]);
  galleryFilterStore.setFilterGenres([
    ...new Set(romsForFilters.flatMap((rom) => rom.metadatum.genres).sort()),
  ]);
  galleryFilterStore.setFilterFranchises([
    ...new Set(
      romsForFilters.flatMap((rom) => rom.metadatum.franchises).sort(),
    ),
  ]);
  galleryFilterStore.setFilterCompanies([
    ...new Set(romsForFilters.flatMap((rom) => rom.metadatum.companies).sort()),
  ]);
  galleryFilterStore.setFilterCollections([
    ...new Set(
      romsForFilters.flatMap((rom) => rom.metadatum.collections).sort(),
    ),
  ]);
  galleryFilterStore.setFilterAgeRatings([
    ...new Set(
      romsForFilters.flatMap((rom) => rom.metadatum.age_ratings).sort(),
    ),
  ]);
  galleryFilterStore.setFilterRegions([
    ...new Set(romsForFilters.flatMap((rom) => rom.regions).sort()),
  ]);
  galleryFilterStore.setFilterLanguages([
    ...new Set(romsForFilters.flatMap((rom) => rom.languages).sort()),
  ]);
}

onMounted(async () => {
  const {
    search: urlSearch,
    matched: urlMatched,
    filterFavorites: urlFilteredFavorites,
    filterDuplicates: urlFilteredDuplicates,
    filterPlayables: urlFilteredPlayables,
    filterMissing: urlFilteredMissing,
    filterVerified: urlFilteredVerified,
    filterRA: urlFilteredRa,
    platform: urlPlatform,
    platforms: urlPlatforms,
    // Single value URL params (backward compatibility)
    genre: urlGenre,
    franchise: urlFranchise,
    collection: urlCollection,
    company: urlCompany,
    ageRating: urlAgeRating,
    region: urlRegion,
    language: urlLanguage,
    status: urlStatus,
    // Multi-value URL params
    genres: urlGenres,
    genresLogic: urlGenresLogic,
    franchises: urlFranchises,
    franchisesLogic: urlFranchisesLogic,
    collections: urlCollections,
    collectionsLogic: urlCollectionsLogic,
    companies: urlCompanies,
    companiesLogic: urlCompaniesLogic,
    ageRatings: urlAgeRatings,
    ageRatingsLogic: urlAgeRatingsLogic,
    regions: urlRegions,
    regionsLogic: urlRegionsLogic,
    languages: urlLanguages,
    languagesLogic: urlLanguagesLogic,
    statuses: urlStatuses,
    statusesLogic: urlStatusesLogic,
  } = router.currentRoute.value.query;

  // Check for query params to set filters
  if (urlMatched !== undefined) {
    if (urlMatched === "1") {
      galleryFilterStore.setFilterMatched(true);
    } else if (urlMatched === "2") {
      galleryFilterStore.setFilterUnmatched(true);
    }
    // urlMatched === "0" or any other value means no filter (both remain null)
  }
  if (urlFilteredFavorites !== undefined) {
    galleryFilterStore.setFilterFavorites(
      urlFilteredFavorites === "1"
        ? true
        : urlFilteredFavorites === "0"
          ? false
          : null,
    );
  }
  if (urlFilteredDuplicates !== undefined) {
    galleryFilterStore.setFilterDuplicates(
      urlFilteredDuplicates === "1"
        ? true
        : urlFilteredDuplicates === "0"
          ? false
          : null,
    );
  }
  if (urlFilteredPlayables !== undefined) {
    galleryFilterStore.setFilterPlayables(
      urlFilteredPlayables === "1"
        ? true
        : urlFilteredPlayables === "0"
          ? false
          : null,
    );
  }
  if (urlFilteredMissing !== undefined) {
    galleryFilterStore.setFilterMissing(
      urlFilteredMissing === "1"
        ? true
        : urlFilteredMissing === "0"
          ? false
          : null,
    );
  }
  if (urlFilteredVerified !== undefined) {
    galleryFilterStore.setFilterVerified(
      urlFilteredVerified === "1"
        ? true
        : urlFilteredVerified === "0"
          ? false
          : null,
    );
  }
  if (urlFilteredRa !== undefined) {
    galleryFilterStore.setFilterRA(
      urlFilteredRa === "1" ? true : urlFilteredRa === "0" ? false : null,
    );
  }
  // Check for query params to set multi-value filters (prioritize over single values)
  if (urlPlatforms !== undefined) {
    const platformIds = (urlPlatforms as string)
      .split(",")
      .filter((p) => p.trim())
      .map(Number);
    const platforms = platformIds
      .map((id) => platformsStore.get(id))
      .filter((p): p is NonNullable<typeof p> => p !== undefined);
    if (platforms.length > 0) {
      galleryFilterStore.setSelectedFilterPlatforms(platforms);
    }
  } else if (urlPlatform !== undefined) {
    // Backward compatibility: if single platform is set, convert to multiselect
    const platform = platformsStore.get(Number(urlPlatform));
    if (platform) galleryFilterStore.setSelectedFilterPlatforms([platform]);
  }
  if (urlGenres !== undefined) {
    const genres = (urlGenres as string).split(",").filter((g) => g.trim());
    galleryFilterStore.setSelectedFilterGenres(genres);
    if (urlGenresLogic !== undefined) {
      galleryFilterStore.setGenresLogic(urlGenresLogic as "any" | "all");
    }
  } else if (urlGenre !== undefined) {
    // Backward compatibility: if single genre is set, convert to multiselect
    galleryFilterStore.setSelectedFilterGenres([urlGenre as string]);
  }

  if (urlFranchises !== undefined) {
    const franchises = (urlFranchises as string)
      .split(",")
      .filter((f) => f.trim());
    galleryFilterStore.setSelectedFilterFranchises(franchises);
    if (urlFranchisesLogic !== undefined) {
      galleryFilterStore.setFranchisesLogic(
        urlFranchisesLogic as "any" | "all",
      );
    }
  } else if (urlFranchise !== undefined) {
    galleryFilterStore.setSelectedFilterFranchises([urlFranchise as string]);
  }

  if (urlCollections !== undefined) {
    const collections = (urlCollections as string)
      .split(",")
      .filter((c) => c.trim());
    galleryFilterStore.setSelectedFilterCollections(collections);
    if (urlCollectionsLogic !== undefined) {
      galleryFilterStore.setCollectionsLogic(
        urlCollectionsLogic as "any" | "all",
      );
    }
  } else if (urlCollection !== undefined) {
    galleryFilterStore.setSelectedFilterCollections([urlCollection as string]);
  }

  if (urlCompanies !== undefined) {
    const companies = (urlCompanies as string)
      .split(",")
      .filter((c) => c.trim());
    galleryFilterStore.setSelectedFilterCompanies(companies);
    if (urlCompaniesLogic !== undefined) {
      galleryFilterStore.setCompaniesLogic(urlCompaniesLogic as "any" | "all");
    }
  } else if (urlCompany !== undefined) {
    galleryFilterStore.setSelectedFilterCompanies([urlCompany as string]);
  }

  if (urlAgeRatings !== undefined) {
    const ageRatings = (urlAgeRatings as string)
      .split(",")
      .filter((a) => a.trim());
    galleryFilterStore.setSelectedFilterAgeRatings(ageRatings);
    if (urlAgeRatingsLogic !== undefined) {
      galleryFilterStore.setAgeRatingsLogic(
        urlAgeRatingsLogic as "any" | "all",
      );
    }
  } else if (urlAgeRating !== undefined) {
    galleryFilterStore.setSelectedFilterAgeRatings([urlAgeRating as string]);
  }

  if (urlRegions !== undefined) {
    const regions = (urlRegions as string).split(",").filter((r) => r.trim());
    galleryFilterStore.setSelectedFilterRegions(regions);
    if (urlRegionsLogic !== undefined) {
      galleryFilterStore.setRegionsLogic(urlRegionsLogic as "any" | "all");
    }
  } else if (urlRegion !== undefined) {
    galleryFilterStore.setSelectedFilterRegions([urlRegion as string]);
  }

  if (urlLanguages !== undefined) {
    const languages = (urlLanguages as string)
      .split(",")
      .filter((l) => l.trim());
    galleryFilterStore.setSelectedFilterLanguages(languages);
    if (urlLanguagesLogic !== undefined) {
      galleryFilterStore.setLanguagesLogic(urlLanguagesLogic as "any" | "all");
    }
  } else if (urlLanguage !== undefined) {
    galleryFilterStore.setSelectedFilterLanguages([urlLanguage as string]);
  }

  if (urlStatuses !== undefined) {
    const statuses = (urlStatuses as string).split(",").filter((s) => s.trim());
    galleryFilterStore.setSelectedFilterStatuses(statuses);
    if (urlStatusesLogic !== undefined) {
      galleryFilterStore.setStatusesLogic(urlStatusesLogic as "any" | "all");
    }
  } else if (urlStatus !== undefined) {
    galleryFilterStore.setSelectedFilterStatuses([urlStatus as string]);
  }

  // Check if search term is set in the URL (empty string is ok)
  const freshSearch = urlSearch !== undefined && urlSearch !== searchTerm.value;
  if (freshSearch) {
    searchTerm.value = urlSearch as string;
    romsStore.resetPagination();
  }

  // Initial fetch of search-filtered ROMs for filter options
  await fetchSearchFilteredRoms();
  setFilters();

  // Fire off search if URL state prepopulated
  if (freshSearch || galleryFilterStore.isFiltered()) {
    emitter?.emit("filterRoms", null);
  }

  // Watch for search term changes to update filter options
  watch(
    () => searchTerm.value,
    async () => {
      await onSearchChange();
    },
    { immediate: false },
  );

  // Watch for platform changes to update filter options
  watch(
    () => allPlatforms.value,
    async () => {
      await fetchSearchFilteredRoms();
      setFilters();
    },
    { immediate: false },
  );
});
</script>

<template>
  <v-navigation-drawer
    v-model="activeFilterDrawer"
    mobile
    floating
    width="500"
    :class="{
      'ml-2': activeFilterDrawer,
      'drawer-mobile': smAndDown && activeFilterDrawer,
    }"
    class="bg-surface rounded mt-4 mb-2 pa-1 unset-height"
  >
    <v-list tabindex="-1">
      <v-list-item v-if="showSearchBar && xs">
        <SearchTextField :tabindex="activeFilterDrawer ? 0 : -1" />
      </v-list-item>
      <v-list-item>
        <FilterMatchStateBtn :tabindex="activeFilterDrawer ? 0 : -1" />
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
      <v-list-item v-if="showPlatformsFilter">
        <FilterPlatformBtn :tabindex="activeFilterDrawer ? 0 : -1" />
      </v-list-item>
      <v-list-item
        v-for="filter in filters"
        :key="filter.label"
        :tabindex="activeFilterDrawer ? 0 : -1"
        class="py-2"
      >
        <div class="d-flex align-center ga-2 w-100">
          <v-select
            v-model="filter.selected.value"
            :tabindex="activeFilterDrawer ? 0 : -1"
            hide-details
            clearable
            multiple
            chips
            closable-chips
            :label="filter.label"
            variant="outlined"
            density="comfortable"
            :items="filter.items.value"
            class="flex-grow-1"
            @update:model-value="
              nextTick(() => emitter?.emit('filterRoms', null))
            "
          />
          <!-- AND/OR Logic Toggle - always visible -->
          <v-btn-toggle
            :model-value="filter.logic.value"
            mandatory
            variant="outlined"
            density="compact"
            class="flex-shrink-0"
            @update:model-value="
              (value) => {
                filter.setLogic(value);
                nextTick(() => emitter?.emit('filterRoms', null));
              }
            "
          >
            <v-tooltip
              text="Match ANY of the selected values (OR logic)"
              location="bottom"
              open-delay="500"
            >
              <template #activator="{ props }">
                <v-btn value="any" size="small" v-bind="props">
                  <v-icon size="x-large">mdi-set-none</v-icon>
                </v-btn>
              </template>
            </v-tooltip>
            <v-tooltip
              text="Match ALL of the selected values (AND logic)"
              location="bottom"
              open-delay="500"
            >
              <template #activator="{ props }">
                <v-btn value="all" size="small" v-bind="props">
                  <v-icon size="x-large">mdi-set-all</v-icon>
                </v-btn>
              </template>
            </v-tooltip>
          </v-btn-toggle>
        </div>
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
