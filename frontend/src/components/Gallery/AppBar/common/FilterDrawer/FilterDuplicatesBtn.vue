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
const { filterDuplicates } = storeToRefs(galleryFilterStore);
const emitter = inject<Emitter<Events>>("emitter");
function setDuplicates() {
  galleryFilterStore.switchFilterDuplicates();
  emitter?.emit("filter", null);
}
</script>

<template>
  <v-btn
    block
    variant="tonal"
    :color="filterDuplicates ? 'primary' : ''"
    @click="setDuplicates()"
  >
    <v-icon :color="filterDuplicates ? 'primary' : ''"
      >mdi-content-duplicate</v-icon
    ><span
      class="ml-2"
      :class="{
        'text-primary': filterDuplicates,
      }"
      >{{ t("platform.show-duplicates") }}</span
    ></v-btn
  >
</template>
