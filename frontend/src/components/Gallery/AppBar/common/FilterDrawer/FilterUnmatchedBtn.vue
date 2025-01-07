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
const { filterUnmatched } = storeToRefs(galleryFilterStore);
const emitter = inject<Emitter<Events>>("emitter");
function setUnmatched() {
  galleryFilterStore.switchFilterUnmatched();
  emitter?.emit("filter", null);
}
</script>

<template>
  <v-btn
    block
    variant="tonal"
    rounded="0"
    :color="filterUnmatched ? 'romm-accent-1' : 'romm-gray'"
    @click="setUnmatched()"
  >
    <v-icon :color="filterUnmatched ? 'romm-accent-1' : 'romm-white'"
      >mdi-file-find-outline</v-icon
    ><span
      class="ml-2"
      :class="{
        'text-romm-white': !filterUnmatched,
        'text-romm-accent-1': filterUnmatched,
      }"
      >{{ t("platform.show-unmatched") }}</span
    ></v-btn
  >
</template>
