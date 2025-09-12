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
const { filterPlayables } = storeToRefs(galleryFilterStore);
const emitter = inject<Emitter<Events>>("emitter");

function setPlayables() {
  galleryFilterStore.switchFilterPlayables();
  emitter?.emit("filterRoms", null);
}
</script>

<template>
  <v-btn
    block
    variant="tonal"
    :color="filterPlayables ? 'primary' : ''"
    :disabled="fetchTotalRoms > 10000"
    @click="setPlayables"
  >
    <v-icon :color="filterPlayables ? 'primary' : ''"> mdi-play </v-icon>
    <span
      class="ml-2"
      :class="{
        'text-primary': filterPlayables,
      }"
      >{{ t("platform.show-playables") }}
    </span>
  </v-btn>
</template>
