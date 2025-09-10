<script setup lang="ts">
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import { inject } from "vue";
import { useI18n } from "vue-i18n";
import storeGalleryFilter from "@/stores/galleryFilter";
import storeRoms from "@/stores/roms";
import type { Events } from "@/types/emitter";

const { t } = useI18n();
const romsStore = storeRoms();
const galleryFilterStore = storeGalleryFilter();
const { fetchTotalRoms } = storeToRefs(romsStore);
const { filterRA } = storeToRefs(galleryFilterStore);
const emitter = inject<Emitter<Events>>("emitter");

function setRA() {
  galleryFilterStore.switchFilterRA();
  emitter?.emit("filterRoms", null);
}
</script>

<template>
  <v-btn
    block
    variant="tonal"
    :color="filterRA ? 'primary' : ''"
    :disabled="fetchTotalRoms > 10000"
    @click="setRA"
  >
    <v-icon :color="filterRA ? 'primary' : ''"> mdi-trophy </v-icon>
    <span
      class="ml-2"
      :class="{
        'text-primary': filterRA,
      }"
      >{{ t("platform.show-ra") }}
    </span>
  </v-btn>
</template>
