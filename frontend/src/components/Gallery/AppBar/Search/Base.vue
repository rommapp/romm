<script setup lang="ts">
import FilterBtn from "@/components/Gallery/AppBar/common/FilterBtn.vue";
import FilterDrawer from "@/components/Gallery/AppBar/common/FilterDrawer/Base.vue";
import GalleryViewBtn from "@/components/Gallery/AppBar/common/GalleryViewBtn.vue";
import SearchTextField from "@/components/Gallery/AppBar/Search/SearchTextField.vue";
import PlatformSelector from "@/components/Gallery/AppBar/Search/PlatformSelector.vue";
import SelectingBtn from "@/components/Gallery/AppBar/common/SelectingBtn.vue";
import SearchBtn from "@/components/Gallery/AppBar/Search/SearchBtn.vue";
import storeRoms from "@/stores/roms";
import { storeToRefs } from "pinia";
import { useDisplay } from "vuetify";
import type { Platform } from "@/types/platform";
import romApi from "@/services/api/rom";
import storeGalleryFilter from "@/stores/galleryFilter";
import type { Events } from "@/types/emitter";
import { inject, ref } from "vue";
import { useI18n } from "vue-i18n";

// Props
const { xs } = useDisplay();
const romsStore = storeRoms();
const { t } = useI18n();
const searching = ref(false);
const searched = ref(false);
const searchedRoms = ref<Platform[]>([]);
const selectedPlatform = ref<Platform | null>(null);
const emitter = inject<Emitter<Events>>("emitter");
const galleryFilterStore = storeGalleryFilter();
const { searchText, filterPlatforms } = storeToRefs(galleryFilterStore);

// Functions
async function fetchRoms() {
  if (searchText.value) {
    // Auto hide android keyboard
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
  <v-app-bar
    id="gallery-app-bar"
    elevation="0"
    density="compact"
    mode="shift"
    app
    fixed
    top
  >
    <filter-btn />
    <template v-if="!xs">
      <search-text-field />
      <platform-selector />
    </template>
    <template #append>
      <search-btn v-if="!xs" />
      <selecting-btn />
      <gallery-view-btn />
    </template>
  </v-app-bar>

  <filter-drawer />
</template>

<style scoped>
#gallery-app-bar {
  z-index: 999 !important;
}
</style>
