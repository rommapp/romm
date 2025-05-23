<script setup lang="ts">
import storeRoms from "@/stores/roms";
import storeGalleryFilter from "@/stores/galleryFilter";
import storeGalleryView from "@/stores/galleryView";
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import { inject, watch, computed } from "vue";
import { useDisplay } from "vuetify";

// Props
const { smAndDown } = useDisplay();
const romsStore = storeRoms();
const galleryFilterStore = storeGalleryFilter();
const galleryViewStore = storeGalleryView();
const { selectedRoms } = storeToRefs(romsStore);
const emitter = inject<Emitter<Events>>("emitter");

const { characterIndex, selectedCharacter, fetchingRoms } =
  storeToRefs(romsStore);

const { scrolledToTop } = storeToRefs(galleryViewStore);

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

const calculatedHeight = computed(() => {
  if (smAndDown.value) {
    if (!scrolledToTop.value && selectedRoms.value.length > 0) {
      return "calc(100dvh - 276px)";
    } else if (!scrolledToTop.value || selectedRoms.value.length > 0) {
      return "calc(100dvh - 225px)";
    } else {
      return "calc(100dvh - 174px)";
    }
  } else {
    if (!scrolledToTop.value && selectedRoms.value.length > 0) {
      return "calc(100dvh - 176px)";
    } else if (!scrolledToTop.value || selectedRoms.value.length > 0) {
      return "calc(100dvh - 125px)";
    } else {
      return "calc(100dvh - 74px)";
    }
  }
});

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
    :style="{
      'max-height': calculatedHeight,
    }"
  >
    <v-tabs
      v-model="selectedCharacter"
      :mandatory="false"
      slider-color="primary"
      bg-color="surface"
      direction="vertical"
      tabindex="-1"
    >
      <v-tab
        v-for="char in Object.keys(characterIndex)"
        :key="char"
        :value="char"
        class="py-3"
      >
        {{ char }}
      </v-tab>
    </v-tabs>
  </v-toolbar>
</template>

<style scoped>
.char-index-toolbar {
  right: 8px;
  transform: translateY(0px);
  height: fit-content;
  width: 44px;
  overflow-y: scroll;
  scrollbar-width: none;
}
</style>
