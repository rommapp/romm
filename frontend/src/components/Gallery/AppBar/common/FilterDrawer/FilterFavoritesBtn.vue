<script setup lang="ts">
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import { inject } from "vue";
import { useI18n } from "vue-i18n";
import storeGalleryFilter from "@/stores/galleryFilter";
import type { Events } from "@/types/emitter";

const { t } = useI18n();
const galleryFilterStore = storeGalleryFilter();
const { filterFavorites } = storeToRefs(galleryFilterStore);
const emitter = inject<Emitter<Events>>("emitter");
function setFavorites() {
  galleryFilterStore.switchFilterFavorites();
  emitter?.emit("filterRoms", null);
}
</script>

<template>
  <v-btn
    block
    variant="tonal"
    :color="filterFavorites ? 'primary' : ''"
    @click="setFavorites"
  >
    <v-icon :color="filterFavorites ? 'primary' : ''"> mdi-star </v-icon
    ><span
      class="ml-2"
      :class="{
        'text-primary': filterFavorites,
      }"
      >{{ t("platform.show-favorites") }}</span
    >
  </v-btn>
</template>
