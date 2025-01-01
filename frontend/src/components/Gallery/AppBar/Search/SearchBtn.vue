<script setup lang="ts">
import { ref, inject } from "vue";
import { useI18n } from "vue-i18n";
import storeRoms from "@/stores/roms";
import romApi from "@/services/api/rom";
import storeGalleryFilter from "@/stores/galleryFilter";
import { storeToRefs } from "pinia";
import type { Platform } from "@/stores/platforms";
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";

const { t } = useI18n();
const romsStore = storeRoms();
const { gettingRoms } = storeToRefs(romsStore);
const searched = ref(false);
const selectedPlatform = ref<Platform | null>(null);
const emitter = inject<Emitter<Events>>("emitter");
const galleryFilterStore = storeGalleryFilter();
const { searchText } = storeToRefs(galleryFilterStore);

function fetchRoms() {
  if (searchText.value) {
    gettingRoms.value = true;
    const inputElement = document.getElementById("search-text-field");
    inputElement?.blur();
    searched.value = true;
    romApi
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
        gettingRoms.value = false;
      });
    filterRoms();
    galleryFilterStore.activeFilterDrawer = false;
  }
}

function filterRoms() {
  if (selectedPlatform.value) {
    romsStore.setFiltered(
      romsStore.allRoms.filter(
        (rom) => rom.platform_id === selectedPlatform.value?.id,
      ),
      galleryFilterStore,
    );
  } else {
    romsStore.setFiltered(romsStore.allRoms, galleryFilterStore);
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
    :disabled="gettingRoms || !searchText"
  />
</template>
