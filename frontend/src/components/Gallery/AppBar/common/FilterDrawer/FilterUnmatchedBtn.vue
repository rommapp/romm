<script setup lang="ts">
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import { inject } from "vue";
import { useI18n } from "vue-i18n";
import storeGalleryFilter from "@/stores/galleryFilter";
import type { Events } from "@/types/emitter";

const { t } = useI18n();
const galleryFilterStore = storeGalleryFilter();
const { filterUnmatched } = storeToRefs(galleryFilterStore);
const emitter = inject<Emitter<Events>>("emitter");
function setUnmatched() {
  galleryFilterStore.switchFilterUnmatched();
  emitter?.emit("filterRoms", null);
}
</script>

<template>
  <v-btn
    block
    variant="tonal"
    :color="filterUnmatched ? 'primary' : ''"
    @click="setUnmatched"
  >
    <v-icon :color="filterUnmatched ? 'primary' : ''">
      mdi-file-find-outline </v-icon
    ><span
      class="ml-2"
      :class="{
        'text-primary': filterUnmatched,
      }"
      >{{ t("platform.show-unmatched") }}</span
    >
  </v-btn>
</template>
