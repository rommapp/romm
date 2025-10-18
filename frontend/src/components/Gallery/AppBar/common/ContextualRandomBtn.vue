<script setup lang="ts">
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import { inject } from "vue";
import { useI18n } from "vue-i18n";
import { useRouter } from "vue-router";
import { ROUTES } from "@/plugins/router";
import romApi from "@/services/api/rom";
import storeGalleryFilter from "@/stores/galleryFilter";
import storeRoms from "@/stores/roms";
import type { Events } from "@/types/emitter";

const { t } = useI18n();
const router = useRouter();
const emitter = inject<Emitter<Events>>("emitter");
const galleryFilterStore = storeGalleryFilter();
const romsStore = storeRoms();
const {
  currentPlatform,
  currentCollection,
  currentVirtualCollection,
  currentSmartCollection,
} = storeToRefs(romsStore);

const {
  searchTerm,
  filterUnmatched,
  filterMatched,
  filterFavorites,
  filterDuplicates,
  filterPlayables,
  filterRA,
  filterMissing,
  filterVerified,
  selectedGenre,
  selectedFranchise,
  selectedCollection,
  selectedCompany,
  selectedAgeRating,
  selectedStatus,
  selectedRegion,
  selectedLanguage,
} = storeToRefs(galleryFilterStore);

async function goToRandomGame() {
  try {
    const apiParams = {
      limit: 1,
      offset: 0,
      platformId: currentPlatform.value?.id || null,
      collectionId: currentCollection.value?.id || null,
      virtualCollectionId: currentVirtualCollection.value?.id || null,
      smartCollectionId: currentSmartCollection.value?.id || null,
      searchTerm:
        searchTerm.value && searchTerm.value.trim()
          ? searchTerm.value.trim()
          : null,
      filterUnmatched: filterUnmatched.value,
      filterMatched: filterMatched.value,
      filterFavorites: filterFavorites.value,
      filterDuplicates: filterDuplicates.value,
      filterPlayables: filterPlayables.value,
      filterRA: filterRA.value,
      filterMissing: filterMissing.value,
      filterVerified: filterVerified.value,
      selectedGenre: selectedGenre.value,
      selectedFranchise: selectedFranchise.value,
      selectedCollection: selectedCollection.value,
      selectedCompany: selectedCompany.value,
      selectedAgeRating: selectedAgeRating.value,
      selectedStatus: selectedStatus.value,
      selectedRegion: selectedRegion.value,
      selectedLanguage: selectedLanguage.value,
    };

    // Get the total count first
    const { data: romsResponse } = await romApi.getRoms(apiParams);

    if (!romsResponse.total || romsResponse.total === 0) {
      emitter?.emit("snackbarShow", {
        msg: "No games found",
        icon: "mdi-information",
        color: "info",
        timeout: 3000,
      });
      return;
    }

    // Get a random offset between 0 and total-1
    const randomOffset = Math.floor(Math.random() * romsResponse.total);
    const { data: randomRomResponse } = await romApi.getRoms({
      ...apiParams,
      offset: randomOffset,
    });

    if (randomRomResponse.items.length > 0) {
      const randomRom = randomRomResponse.items[0];
      router.push({ name: ROUTES.ROM, params: { rom: randomRom.id } });
    } else {
      emitter?.emit("snackbarShow", {
        msg: "Could not find a random game",
        icon: "mdi-alert",
        color: "warning",
        timeout: 3000,
      });
    }
  } catch (error) {
    console.error("Error fetching random game:", error);
    emitter?.emit("snackbarShow", {
      msg: "Error finding random game",
      icon: "mdi-close-circle",
      color: "red",
      timeout: 4000,
    });
  }
}
</script>

<template>
  <v-btn
    icon
    variant="text"
    color="text-white"
    :disabled="romsStore.filteredRoms.length === 0"
    rounded="0"
    :title="t('common.random')"
    class="bg-surface ma-0"
    @click="goToRandomGame"
  >
    <v-icon>mdi-shuffle-variant</v-icon>
  </v-btn>
</template>
