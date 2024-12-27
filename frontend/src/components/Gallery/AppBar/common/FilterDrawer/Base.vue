<script setup lang="ts">
import FilterUnmatchedBtn from "@/components/Gallery/AppBar/common/FilterDrawer/FilterUnmatchedBtn.vue";
import FilterMatchedBtn from "@/components/Gallery/AppBar/common/FilterDrawer/FilterMatchedBtn.vue";
import FilterFavouritesBtn from "@/components/Gallery/AppBar/common/FilterDrawer/FilterFavouritesBtn.vue";
import FilterDuplicatesBtn from "@/components/Gallery/AppBar/common/FilterDrawer/FilterDuplicatesBtn.vue";
import FilterTextField from "@/components/Gallery/AppBar/common/FilterTextField.vue";
import PlatformSelector from "@/components/Gallery/AppBar/Search/PlatformSelector.vue";
import SearchTextField from "@/components/Gallery/AppBar/Search/SearchTextField.vue";
import SearchBtn from "@/components/Gallery/AppBar/Search/SearchBtn.vue";
import storeGalleryFilter from "@/stores/galleryFilter";
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import { inject, nextTick, ref } from "vue";
import { useDisplay } from "vuetify";
import { useI18n } from "vue-i18n";

// Props
const { t } = useI18n();
const { xs } = useDisplay();
const viewportWidth = ref(window.innerWidth);
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
  selectedAgeRating,
  filterAgeRatings,
  selectedStatus,
  filterStatuses,
} = storeToRefs(galleryFilterStore);
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
</script>

<template>
  <v-navigation-drawer
    floating
    mobile
    :width="xs ? viewportWidth : '350'"
    @update:model-value="galleryFilterStore.switchActiveFilterDrawer()"
    v-model="activeFilterDrawer"
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
          <v-list-item>
            <platform-selector />
          </v-list-item>
        </template>
      </template>
      <v-list-item>
        <filter-unmatched-btn />
        <filter-matched-btn class="mt-2" />
        <filter-favourites-btn class="mt-2" />
        <filter-duplicates-btn class="mt-2" />
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
          {{ t("platform.reset-filters") }}
        </v-btn>
      </v-list-item>
    </v-list>
  </v-navigation-drawer>
</template>
