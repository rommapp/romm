<script setup lang="ts">
import romApi from "@/services/api/rom";
import storeRoms from "@/stores/roms";
import storeGalleryFilter from "@/stores/galleryFilter";
import storePlatforms from "@/stores/platforms";
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { inject, ref } from "vue";
import { storeToRefs } from "pinia";
import { useDisplay } from "vuetify";
import type { Platform } from "@/stores/platforms";
import { useI18n } from "vue-i18n";

// Props
const { xs } = useDisplay();
const { t } = useI18n();
const romsStore = storeRoms();
const emitter = inject<Emitter<Events>>("emitter");
const searching = ref(false);
const platformsStore = storePlatforms();
const { allPlatforms } = storeToRefs(platformsStore);
const galleryFilterStore = storeGalleryFilter();
const { searchText, filterPlatforms } = storeToRefs(galleryFilterStore);

// Functions
function setFilters() {
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
        .flatMap((rom) => rom.collections.map((collection) => collection))
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

async function fetchRoms() {
  if (searchText.value) {
    // Auto hide android keyboard
    const inputElement = document.getElementById("search-text-field");
    inputElement?.blur();
    searching.value = true;
    await romApi
      .getRoms({ searchTerm: searchText.value })
      .then(({ data }) => {
        data = data.sort((a, b) => {
          return a.platform_name.localeCompare(b.platform_name);
        });
        romsStore.set(data);
        romsStore.setFiltered(data, galleryFilterStore);
      })
      .catch((error) => {
        emitter?.emit("snackbarShow", {
          msg: `Couldn't fetch roms: ${error}`,
          icon: "mdi-close-circle",
          color: "red",
          timeout: 4000,
        });
        console.error(`Couldn't fetch roms: ${error}`);
      })
      .finally(() => {
        searching.value = false;
      });
    galleryFilterStore.setFilterPlatforms([
      ...new Map(
        romsStore.filteredRoms.map((rom) => {
          const platform = allPlatforms.value.find(
            (p) => p.id === rom.platform_id,
          );
          return [rom.platform_name, platform];
        }),
      ).values(),
    ] as Platform[]);
    setFilters();
    searching.value = false;
    galleryFilterStore.activeFilterDrawer = false;
  }
}
</script>

<template>
  <v-text-field
    rounded="0"
    :density="xs ? 'comfortable' : 'default'"
    clearable
    autofocus
    @keyup.enter="fetchRoms"
    v-model="searchText"
    :disabled="searching"
    :label="t('common.search')"
    hide-details
    class="bg-terciary"
  />
</template>
