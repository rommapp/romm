<script setup lang="ts">
import { ref, inject } from "vue";
import storeRoms from "@/stores/roms";
import storeGalleryFilter from "@/stores/galleryFilter";
import { storeToRefs } from "pinia";
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";

const romsStore = storeRoms();
const { fetchingRoms, initialSearch } = storeToRefs(romsStore);
const emitter = inject<Emitter<Events>>("emitter");
const galleryFilterStore = storeGalleryFilter();
const { searchTerm } = storeToRefs(galleryFilterStore);

function fetchRoms() {
  if (searchTerm.value == null) return;

  const inputElement = document.getElementById("search-text-field");
  inputElement?.blur();
  initialSearch.value = true;
  romsStore.fetchRoms(galleryFilterStore).catch((error) => {
    emitter?.emit("snackbarShow", {
      msg: `Couldn't fetch roms: ${error}`,
      icon: "mdi-close-circle",
      color: "red",
      timeout: 4000,
    });
  });

  galleryFilterStore.activeFilterDrawer = false;
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
    :disabled="fetchingRoms || !searchTerm"
  />
</template>
