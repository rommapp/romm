<script setup lang="ts">
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import { inject } from "vue";
import { useI18n } from "vue-i18n";
import storeGalleryFilter from "@/stores/galleryFilter";
import type { Events } from "@/types/emitter";

const { t } = useI18n();
const galleryFilterStore = storeGalleryFilter();
const { filterVerified } = storeToRefs(galleryFilterStore);
const emitter = inject<Emitter<Events>>("emitter");
function setVerified() {
  galleryFilterStore.switchFilterVerified();
  emitter?.emit("filterRoms", null);
}
</script>

<template>
  <v-btn
    block
    variant="tonal"
    :color="filterVerified ? 'primary' : ''"
    @click="setVerified"
  >
    <v-icon :color="filterVerified ? 'primary' : ''">
      mdi-check-decagram </v-icon
    ><span
      class="ml-2"
      :class="{
        'text-primary': filterVerified,
      }"
      >{{ t("platform.show-verified") }}</span
    >
  </v-btn>
</template>
