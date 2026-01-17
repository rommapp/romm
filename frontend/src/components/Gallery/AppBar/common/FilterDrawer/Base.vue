<script setup lang="ts">
import { debounce } from "lodash";
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import { inject, nextTick, onMounted } from "vue";
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
  filterMatched,
  filterFavorites,
  filterDuplicates,
  filterPlayables,
  filterRA,
  filterMissing,
  filterVerified,
  filterGenres,
  selectedGenres,
  genresLogic,
  filterFranchises,
  selectedFranchises,
  franchisesLogic,
  filterCollections,
  selectedCollections,
  collectionsLogic,
  filterCompanies,
  selectedCompanies,
  companiesLogic,
  filterAgeRatings,
  selectedAgeRatings,
  ageRatingsLogic,
  filterStatuses,
  selectedStatuses,
  statusesLogic,
  selectedPlatforms,
  filterRegions,
  selectedRegions,
  regionsLogic,
  filterLanguages,
  selectedLanguages,
  languagesLogic,
  filterPlayerCounts,
  selectedPlayerCounts,
  playerCountsLogic,
} = storeToRefs(galleryFilterStore);
const emitter = inject<Emitter<Events>>("emitter");

const onFilterChange = debounce(
  () => {
    romsStore.resetPagination();
    romsStore.fetchRoms({
      galleryFilter: galleryFilterStore,
      platformsStore: platformsStore,
      concat: false,
    });

    const url = new URL(window.location.href);
    // Update URL with filters
    Object.entries({
      search: searchTerm.value,
      matched:
        filterMatched.value === null ? null : String(filterMatched.value),
      filterFavorites:
        filterFavorites.value === null ? null : String(filterFavorites.value),
      filterDuplicates:
        filterDuplicates.value === null ? null : String(filterDuplicates.value),
      filterPlayables:
        filterPlayables.value === null ? null : String(filterPlayables.value),
      filterMissing:
        filterMissing.value === null ? null : String(filterMissing.value),
      filterVerified:
        filterVerified.value === null ? null : String(filterVerified.value),
      filterRA: filterRA.value === null ? null : String(filterRA.value),
      platforms:
        selectedPlatforms.value.length > 0
          ? selectedPlatforms.value.map((p) => String(p.id)).join(",")
          : null,
      genres:
        selectedGenres.value.length > 0 ? selectedGenres.value.join(",") : null,
      genresLogic: selectedGenres.value.length > 1 ? genresLogic.value : null,
      franchises:
        selectedFranchises.value.length > 0
          ? selectedFranchises.value.join(",")
          : null,
      franchisesLogic:
        selectedFranchises.value.length > 1 ? franchisesLogic.value : null,
      collections:
        selectedCollections.value.length > 0
          ? selectedCollections.value.join(",")
          : null,
      collectionsLogic:
        selectedCollections.value.length > 1 ? collectionsLogic.value : null,
      companies:
        selectedCompanies.value.length > 0
          ? selectedCompanies.value.join(",")
          : null,
      companiesLogic:
        selectedCompanies.value.length > 1 ? companiesLogic.value : null,
      ageRatings:
        selectedAgeRatings.value.length > 0
          ? selectedAgeRatings.value.join(",")
          : null,
      ageRatingsLogic:
        selectedAgeRatings.value.length > 1 ? ageRatingsLogic.value : null,
      regions:
        selectedRegions.value.length > 0
          ? selectedRegions.value.join(",")
          : null,
      regionsLogic:
        selectedRegions.value.length > 1 ? regionsLogic.value : null,
      languages:
        selectedLanguages.value.length > 0
          ? selectedLanguages.value.join(",")
          : null,
      languagesLogic:
        selectedLanguages.value.length > 1 ? languagesLogic.value : null,
      statuses:
        selectedStatuses.value.length > 0
          ? selectedStatuses.value.join(",")
          : null,
      statusesLogic:
        selectedStatuses.value.length > 1 ? statusesLogic.value : null,
      playerCounts:
        selectedPlayerCounts.value.length > 0
          ? selectedPlayerCounts.value.join(",")
          : null,
      playerCountsLogic:
        selectedPlayerCounts.value.length > 0 ? playerCountsLogic.value : null,
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
    label: t("platform.player-count"),
    selected: selectedPlayerCounts,
    items: filterPlayerCounts,
    logic: playerCountsLogic,
    setLogic: (logic: "any" | "all") =>
      galleryFilterStore.setPlayerCountsLogic(logic),
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
    emitter?.emit("filterRoms", null);
  });
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
    playerCounts: urlPlayerCounts,
    playerCountsLogic: urlPlayerCountsLogic,
  } = router.currentRoute.value.query;

  // Check for query params to set filters
  if (urlMatched !== undefined) {
    if (urlMatched === "true") {
      galleryFilterStore.setFilterMatched(true);
    } else if (urlMatched === "false") {
      galleryFilterStore.setFilterMatched(false);
    }
    // Any other value means no filter (both remain null)
  }
  if (urlFilteredFavorites !== undefined) {
    if (urlFilteredFavorites === "true") {
      galleryFilterStore.setFilterFavorites(true);
    } else if (urlFilteredFavorites === "false") {
      galleryFilterStore.setFilterFavorites(false);
    } else {
      galleryFilterStore.setFilterFavorites(null);
    }
  }
  if (urlFilteredDuplicates !== undefined) {
    if (urlFilteredDuplicates === "true") {
      galleryFilterStore.setFilterDuplicates(true);
    } else if (urlFilteredDuplicates === "false") {
      galleryFilterStore.setFilterDuplicates(false);
    } else {
      galleryFilterStore.setFilterDuplicates(null);
    }
  }
  if (urlFilteredPlayables !== undefined) {
    if (urlFilteredPlayables === "true") {
      galleryFilterStore.setFilterPlayables(true);
    } else if (urlFilteredPlayables === "false") {
      galleryFilterStore.setFilterPlayables(false);
    } else {
      galleryFilterStore.setFilterPlayables(null);
    }
  }
  if (urlFilteredMissing !== undefined) {
    if (urlFilteredMissing === "true") {
      galleryFilterStore.setFilterMissing(true);
    } else if (urlFilteredMissing === "false") {
      galleryFilterStore.setFilterMissing(false);
    } else {
      galleryFilterStore.setFilterMissing(null);
    }
  }
  if (urlFilteredVerified !== undefined) {
    if (urlFilteredVerified === "true") {
      galleryFilterStore.setFilterVerified(true);
    } else if (urlFilteredVerified === "false") {
      galleryFilterStore.setFilterVerified(false);
    } else {
      galleryFilterStore.setFilterVerified(null);
    }
  }
  if (urlFilteredRa !== undefined) {
    if (urlFilteredRa === "true") {
      galleryFilterStore.setFilterRA(true);
    } else if (urlFilteredRa === "false") {
      galleryFilterStore.setFilterRA(false);
    } else {
      galleryFilterStore.setFilterRA(null);
    }
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
  }

  if (urlCompanies !== undefined) {
    const companies = (urlCompanies as string)
      .split(",")
      .filter((c) => c.trim());
    galleryFilterStore.setSelectedFilterCompanies(companies);
    if (urlCompaniesLogic !== undefined) {
      galleryFilterStore.setCompaniesLogic(urlCompaniesLogic as "any" | "all");
    }
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
  }

  if (urlRegions !== undefined) {
    const regions = (urlRegions as string).split(",").filter((r) => r.trim());
    galleryFilterStore.setSelectedFilterRegions(regions);
    if (urlRegionsLogic !== undefined) {
      galleryFilterStore.setRegionsLogic(urlRegionsLogic as "any" | "all");
    }
  }

  if (urlLanguages !== undefined) {
    const languages = (urlLanguages as string)
      .split(",")
      .filter((l) => l.trim());
    galleryFilterStore.setSelectedFilterLanguages(languages);
    if (urlLanguagesLogic !== undefined) {
      galleryFilterStore.setLanguagesLogic(urlLanguagesLogic as "any" | "all");
    }
  }

  if (urlStatuses !== undefined) {
    const statuses = (urlStatuses as string).split(",").filter((s) => s.trim());
    galleryFilterStore.setSelectedFilterStatuses(statuses);
    if (urlStatusesLogic !== undefined) {
      galleryFilterStore.setStatusesLogic(urlStatusesLogic as "any" | "all");
    }
  }

  if (urlPlayerCounts !== undefined) {
    const playerCounts = (urlPlayerCounts as string)
      .split(",")
      .filter((pc) => pc.trim());
    galleryFilterStore.setSelectedFilterPlayerCounts(playerCounts);
    if (urlPlayerCountsLogic !== undefined) {
      galleryFilterStore.setPlayerCountsLogic(
        urlPlayerCountsLogic as "any" | "all",
      );
    }
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
              :text="t('platform.match-any-logic')"
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
              :text="t('platform.match-all-logic')"
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
