<script setup lang="ts">
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import { inject } from "vue";
import { useI18n } from "vue-i18n";
import storeGalleryFilter from "@/stores/galleryFilter";
import type { Events } from "@/types/emitter";

const { t } = useI18n();
const galleryFilterStore = storeGalleryFilter();
const { filterFavourites } = storeToRefs(galleryFilterStore);
const emitter = inject<Emitter<Events>>("emitter");
function setFavourites() {
  galleryFilterStore.switchFilterFavourites();
  emitter?.emit("filterRoms", null);
}
</script>

<template>
  <v-btn
    block
    variant="tonal"
    :color="filterFavourites ? 'primary' : ''"
    @click="setFavourites"
  >
    <v-icon :color="filterFavourites ? 'primary' : ''">mdi-star</v-icon
    ><span
      class="ml-2"
      :class="{
        'text-primary': filterFavourites,
      }"
      >{{ t("platform.show-favourites") }}</span
    ></v-btn
  >
</template>
