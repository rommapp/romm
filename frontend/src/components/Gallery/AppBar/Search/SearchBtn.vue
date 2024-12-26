<script setup lang="ts">
import { ref, inject } from "vue";
import { useI18n } from "vue-i18n";
import storeRoms from "@/stores/roms";
import romApi from "@/services/api/rom";
import storeGalleryFilter from "@/stores/galleryFilter";
import { storeToRefs } from "pinia";
import type { Platform } from "@/types/platform";
import type { Events } from "@/types/emitter";

const romsStore = storeRoms();
const { t } = useI18n();
const searching = ref(false);
const searched = ref(false);
const searchedRoms = ref<Platform[]>([]);
const selectedPlatform = ref<Platform | null>(null);
const emitter = inject<Emitter<Events>>("emitter");
const galleryFilterStore = storeGalleryFilter();
const { searchText, filterPlatforms } = storeToRefs(galleryFilterStore);

async function fetchRoms() {
  if (searchText.value) {
    const inputElement = document.getElementById("search-text-field");
    inputElement?.blur();
    searching.value = true;
    searched.value = true;
    await romApi
      .getRoms({ searchTerm: searchText.value })
      .then(({ data }) => {
        data = data.sort((a, b) => {
          return a.platform_name.localeCompare(b.platform_name);
        });
        romsStore.set(data);
        romsStore.setFiltered(data, storeGalleryFilter);
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
    filterPlatforms.value = [
      ...new Map(
        romsStore.filteredRoms.map((rom): [string, Platform] => [
          rom.platform_name,
          {
            platform_name: rom.platform_name,
            platform_slug: rom.platform_slug,
          },
        ]),
      ).values(),
    ];
    searching.value = false;
    filterRoms();
    galleryFilterStore.activeFilterDrawer = false;
  }
}

function clearFilter() {
  selectedPlatform.value = null;
  fetchRoms();
}

function filterRoms() {
  if (selectedPlatform.value) {
    romsStore.setFiltered(
      romsStore.allRoms.filter(
        (rom) => rom.platform_slug === selectedPlatform.value?.platform_slug,
      ),
      storeGalleryFilter,
    );
  } else {
    romsStore.setFiltered(romsStore.allRoms, storeGalleryFilter);
  }
}
</script>

<template>
  <v-btn
    id="search-btn"
    type="submit"
    @click="fetchRoms"
    class="bg-terciary"
    rounded="0"
    variant="text"
    icon="mdi-magnify"
    :disabled="searching || !searchText"
  />
</template>
