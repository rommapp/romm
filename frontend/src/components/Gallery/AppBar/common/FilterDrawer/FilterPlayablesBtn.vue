<script setup lang="ts">
import storeGalleryFilter from "@/stores/galleryFilter";
import storeRoms from "@/stores/roms";
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import { inject } from "vue";
import { useI18n } from "vue-i18n";

// Props
const { t } = useI18n();
const romsStore = storeRoms();
const galleryFilterStore = storeGalleryFilter();
const { fetchTotalRoms } = storeToRefs(romsStore);
const { filterPlayables } = storeToRefs(galleryFilterStore);
const emitter = inject<Emitter<Events>>("emitter");

// Functions
function setPlayables() {
  galleryFilterStore.switchFilterPlayables();
  emitter?.emit("filter", null);
}
</script>

<template>
  <v-btn
    block
    variant="tonal"
    :color="filterPlayables ? 'primary' : ''"
    @click="setPlayables()"
    :disabled="fetchTotalRoms > 10000"
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
