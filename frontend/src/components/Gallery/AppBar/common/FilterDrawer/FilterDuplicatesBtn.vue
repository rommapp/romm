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
const { filterDuplicates } = storeToRefs(galleryFilterStore);
const emitter = inject<Emitter<Events>>("emitter");
function setDuplicates() {
  galleryFilterStore.switchFilterDuplicates();
  emitter?.emit("filterRoms", null);
}
</script>

<template>
  <v-btn
    block
    variant="tonal"
    :color="filterDuplicates ? 'primary' : ''"
    :disabled="fetchTotalRoms > 10000"
    @click="setDuplicates"
  >
    <v-icon :color="filterDuplicates ? 'primary' : ''">
      mdi-card-multiple
    </v-icon>
    <span
      class="ml-2"
      :class="{
        'text-primary': filterDuplicates,
      }"
      >{{ t("platform.show-duplicates") }}
    </span>
  </v-btn>
</template>
