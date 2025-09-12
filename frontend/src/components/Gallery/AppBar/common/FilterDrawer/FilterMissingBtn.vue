<script setup lang="ts">
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import { inject } from "vue";
import { useI18n } from "vue-i18n";
import storeGalleryFilter from "@/stores/galleryFilter";
import type { Events } from "@/types/emitter";

const { t } = useI18n();
const galleryFilterStore = storeGalleryFilter();
const { filterMissing } = storeToRefs(galleryFilterStore);
const emitter = inject<Emitter<Events>>("emitter");
function setMissing() {
  galleryFilterStore.switchFilterMissing();
  emitter?.emit("filterRoms", null);
}
</script>

<template>
  <v-btn
    block
    variant="tonal"
    :color="filterMissing ? 'primary' : ''"
    @click="setMissing"
  >
    <v-icon :color="filterMissing ? 'primary' : ''">
      mdi-folder-question </v-icon
    ><span
      class="ml-2"
      :class="{
        'text-primary': filterMissing,
      }"
      >{{ t("platform.show-missing") }}</span
    >
  </v-btn>
</template>
