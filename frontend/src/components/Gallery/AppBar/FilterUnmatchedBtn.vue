<script setup lang="ts">
import storeGalleryFilter from "@/stores/galleryFilter";
import { storeToRefs } from "pinia";
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { inject } from "vue";

// Props
const galleryFilterStore = storeGalleryFilter();
const { filterUnmatched } = storeToRefs(galleryFilterStore);
const emitter = inject<Emitter<Events>>("emitter");
function setUnmatched() {
  galleryFilterStore.setFilterUnmatched();
  emitter?.emit("filter", null);
}
</script>

<template>
  <v-tooltip
    location="bottom"
    class="tooltip"
    transition="fade-transition"
    text="Filter unmatched games"
    open-delay="1000"
    ><template #activator="{ props }">
      <v-btn
        class="ma-1"
        variant="outlined"
        size="compact"
        :color="filterUnmatched ? 'romm-accent-1' : 'romm-gray'"
        v-bind="props"
        @click="setUnmatched()"
        ><v-icon
          class="mx-5"
          :color="filterUnmatched ? 'romm-accent-1' : 'romm-white'"
          >mdi-file-find-outline</v-icon
        ></v-btn
      ></template
    ></v-tooltip
  >
</template>