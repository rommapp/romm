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
const { filterMatched } = storeToRefs(galleryFilterStore);
const emitter = inject<Emitter<Events>>("emitter");
function setUnmatched() {
  galleryFilterStore.switchFilterMatched();
  emitter?.emit("filter", null);
}
</script>

<template>
  <v-btn
    block
    variant="tonal"
    rounded="0"
    :color="filterMatched ? 'romm-accent-1' : 'romm-gray'"
    @click="setUnmatched()"
  >
    <v-icon :color="filterMatched ? 'romm-accent-1' : 'romm-white'"
      >mdi-file-find</v-icon
    ><span
      class="ml-2"
      :class="{
        'text-romm-white': !filterMatched,
        'text-romm-accent-1': filterMatched,
      }"
      >{{ t("platform.show-matched") }}</span
    ></v-btn
  >
</template>
