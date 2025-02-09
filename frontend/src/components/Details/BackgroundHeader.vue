<script setup lang="ts">
import storeRoms from "@/stores/roms";
import { getMissingCoverImage, getUnmatchedCoverImage } from "@/utils/covers";
import { storeToRefs } from "pinia";
import { computed } from "vue";

// Props
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
    id="background-header"
    elevation="0"
    rounded="0"
    :key="currentRom.updated_at"
    v-if="currentRom"
  >
    <v-img
      id="background-image"
      :src="
        currentRom?.path_cover_large ||
        unmatchedCoverImage
      "
      lazy
      cover
    >
      <template #error>
        <v-img :src="missingCoverImage" />
      </template>
      <template #placeholder>
        <div class="d-flex align-center justify-center fill-height">
          <v-progress-circular
            :width="2"
            :size="40"
            color="primary"
            indeterminate
          />
        </div>
      </template>
    </v-img>
  </v-card>
</template>
<style scoped>
#background-header {
  width: 100%;
}

#background-image {
  height: 18rem;
  filter: blur(30px);
}
</style>
