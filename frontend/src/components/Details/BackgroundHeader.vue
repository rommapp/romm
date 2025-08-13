<script setup lang="ts">
import storeRoms from "@/stores/roms";
import { getMissingCoverImage, getUnmatchedCoverImage } from "@/utils/covers";
import { storeToRefs } from "pinia";
import { computed } from "vue";
import { useRouter } from "vue-router";

const romsStore = storeRoms();
const { currentRom, filteredRoms } = storeToRefs(romsStore);
const router = useRouter();

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

const currentRomIndex = computed(() =>
  filteredRoms.value.findIndex((rom) => rom.id === currentRom.value?.id),
);

function previousRom() {
  if (currentRomIndex.value > 0) {
    router.push(`/rom/${filteredRoms.value[currentRomIndex.value - 1].id}`);
  }
}

function nextRom() {
  if (currentRomIndex.value < filteredRoms.value.length - 1) {
    router.push(`/rom/${filteredRoms.value[currentRomIndex.value + 1].id}`);
  }
}
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
      :src="currentRom?.path_cover_large || unmatchedCoverImage"
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
  <v-row
    v-if="filteredRoms.length > 1"
    no-gutters
    class="justify-center mt-2 position-absolute top-0 right-0 mr-2"
  >
    <v-btn-group>
      <v-btn size="small" :disabled="currentRomIndex <= 0" @click="previousRom">
        <v-icon>mdi-arrow-left</v-icon>
        <span class="d-none d-sm-block">{{
          filteredRoms[currentRomIndex - 1].name
        }}</span>
      </v-btn>
      <v-btn
        size="small"
        :disabled="currentRomIndex === filteredRoms.length - 1"
        @click="nextRom"
      >
        <span class="d-none d-sm-block">{{
          filteredRoms[currentRomIndex + 1].name
        }}</span>
        <v-icon>mdi-arrow-right</v-icon>
      </v-btn>
    </v-btn-group>
  </v-row>
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
