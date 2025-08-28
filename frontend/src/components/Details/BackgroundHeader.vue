<script setup lang="ts">
import storeRoms from "@/stores/roms";
import { getMissingCoverImage, getUnmatchedCoverImage } from "@/utils/covers";
import { storeToRefs } from "pinia";
import { computed } from "vue";

const romsStore = storeRoms();
const { currentRom } = storeToRefs(romsStore);
const missingCoverImage = computed(() =>
  getMissingCoverImage(
    currentRom.value?.name || currentRom.value?.fs_name || "",
  ),
);
const unmatchedCoverImage = computed(() =>
  getUnmatchedCoverImage(
    currentRom.value?.name || currentRom.value?.fs_name || "",
  ),
);
</script>

<template>
  <v-card
    elevation="0"
    rounded="0"
    class="w-100"
    :key="currentRom.updated_at"
    v-if="currentRom"
  >
    <v-img
      class="background-image"
      :src="currentRom?.path_cover_small || unmatchedCoverImage"
      cover
    >
      <template #error>
        <v-img :src="missingCoverImage" />
      </template>
      <template #placeholder>
        <v-skeleton-loader class="background-skeleton" type="image" />
      </template>
    </v-img>
  </v-card>
</template>

<style scoped>
.background-image {
  height: 18rem;
  filter: blur(30px);
}

.background-skeleton {
  height: 18rem;
}
</style>

<style>
.background-skeleton .v-skeleton-loader__image {
  height: 100%;
}
</style>
