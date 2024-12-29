<script setup lang="ts">
import storeGalleryFilter from "@/stores/galleryFilter";
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import { inject } from "vue";
import { useI18n } from "vue-i18n";

// Props
const { t } = useI18n();
const galleryFilterStore = storeGalleryFilter();
const { filterFavourites } = storeToRefs(galleryFilterStore);
const emitter = inject<Emitter<Events>>("emitter");
function setFavourites() {
  galleryFilterStore.switchFilterFavourites();
  emitter?.emit("filter", null);
}
</script>

<template>
  <v-btn
    block
    variant="tonal"
    rounded="0"
    :color="filterFavourites ? 'romm-accent-1' : 'romm-gray'"
    @click="setFavourites()"
  >
    <v-icon :color="filterFavourites ? 'romm-accent-1' : 'romm-white'"
      >mdi-star</v-icon
    ><span
      class="ml-2"
      :class="{
        'text-romm-white': !filterFavourites,
        'text-romm-accent-1': filterFavourites,
      }"
      >{{ t("platform.show-favourites") }}</span
    ></v-btn
  >
</template>
