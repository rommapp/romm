<script setup lang="ts">
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import { inject } from "vue";
import { useI18n } from "vue-i18n";
import storeGalleryFilter from "@/stores/galleryFilter";
import type { Events } from "@/types/emitter";

const { t } = useI18n();
const galleryFilterStore = storeGalleryFilter();
const { filterMatched } = storeToRefs(galleryFilterStore);
const emitter = inject<Emitter<Events>>("emitter");
function setUnmatched() {
  galleryFilterStore.switchFilterMatched();
  emitter?.emit("filterRoms", null);
}
</script>

<template>
  <v-btn
    block
    variant="tonal"
    :color="filterMatched ? 'primary' : ''"
    @click="setUnmatched"
  >
    <v-icon :color="filterMatched ? 'primary' : ''"> mdi-file-find </v-icon
    ><span
      class="ml-2"
      :class="{
        'text-primary': filterMatched,
      }"
      >{{ t("platform.show-matched") }}</span
    >
  </v-btn>
</template>
