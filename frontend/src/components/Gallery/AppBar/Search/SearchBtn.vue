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

const romsStore = storeRoms();
const { fetchingRoms } = storeToRefs(romsStore);
const searched = ref(false);
const selectedPlatform = ref<Platform | null>(null);
const emitter = inject<Emitter<Events>>("emitter");
const galleryFilterStore = storeGalleryFilter();
const { searchText } = storeToRefs(galleryFilterStore);

function fetchRoms() {
  if (searchText.value == null) return;

  const inputElement = document.getElementById("search-text-field");
  inputElement?.blur();
  searched.value = true;

  romsStore
    .fetchRoms({ searchTerm: searchText.value }, galleryFilterStore)
    .catch((error) => {
      emitter?.emit("snackbarShow", {
        msg: `Couldn't fetch roms: ${error}`,
        icon: "mdi-close-circle",
        color: "red",
        timeout: 4000,
      });
    });

  filterRoms();
  galleryFilterStore.activeFilterDrawer = false;
}

function filterRoms() {
  if (selectedPlatform.value) {
    galleryFilterStore.setFilterPlatforms([selectedPlatform.value]);
  }
  romsStore.setFiltered(galleryFilterStore);
}
</script>

<template>
  <v-btn
    rounded="0"
    id="search-btn"
    type="submit"
    @click="fetchRoms"
    class="bg-toplayer"
    variant="text"
    icon="mdi-magnify"
    :disabled="fetchingRoms || !searchText"
  />
</template>
