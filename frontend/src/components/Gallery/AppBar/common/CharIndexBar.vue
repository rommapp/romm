<script setup lang="ts">
import storeRoms from "@/stores/roms";
import storeGalleryFilter from "@/stores/galleryFilter";
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import { inject, watch } from "vue";

const romsStore = storeRoms();
const galleryFilterStore = storeGalleryFilter();
const emitter = inject<Emitter<Events>>("emitter");

const { characterIndex, selectedCharacter, fetchingRoms } =
  storeToRefs(romsStore);

async function fetchRoms() {
  if (fetchingRoms.value) return;

  emitter?.emit("showLoadingDialog", {
    loading: true,
    scrim: false,
  });

  romsStore
    .fetchRoms(galleryFilterStore, false)
    .then(() => {
      emitter?.emit("showLoadingDialog", {
        loading: false,
        scrim: false,
      });
    })
    .catch((error) => {
      emitter?.emit("snackbarShow", {
        msg: `Couldn't fetch roms: ${error}`,
        icon: "mdi-close-circle",
        color: "red",
        timeout: 4000,
      });
      emitter?.emit("showLoadingDialog", {
        loading: false,
        scrim: false,
      });
    });
}

watch(
  selectedCharacter,
  () => {
    if (!selectedCharacter.value) return;
    romsStore.resetPagination();
    romsStore.fetchOffset = characterIndex.value[selectedCharacter.value];
    fetchRoms();
  },
  { immediate: true },
);
</script>

<template>
  <v-toolbar
    elevation="0"
    density="compact"
    rounded
    height="100%"
    class="position-fixed bg-surface mt-4 char-index-toolbar"
  >
    <v-tabs v-model="selectedCharacter" bg-color="surface" direction="vertical">
      <v-tab
        v-for="char in Object.keys(characterIndex)"
        :key="char"
        :value="char"
        class="py-4"
      >
        {{ char }}
      </v-tab>
    </v-tabs>
  </v-toolbar>
</template>

<style scoped>
.char-index-toolbar {
  right: 8px;
  z-index: 1010;
  transform: translateY(0px);
  height: fit-content;
  max-height: calc(100vh - 74px);
  width: 44px;
  overflow-y: scroll;
  scrollbar-width: none;
}
</style>
