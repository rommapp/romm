<script setup lang="ts">
import { storeToRefs } from "pinia";
import { computed } from "vue";
import { useRouter } from "vue-router";
import { useDisplay } from "vuetify";
import storeRoms from "@/stores/roms";
import { getMissingCoverImage, getUnmatchedCoverImage } from "@/utils/covers";

const romsStore = storeRoms();
const { currentRom, romIdIndex } = storeToRefs(romsStore);
const router = useRouter();
const { smAndUp } = useDisplay();

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
  romIdIndex.value.findIndex((rom) => rom === currentRom.value?.id),
);

function previousRom() {
  if (currentRomIndex.value > 0) {
    router.push(`/rom/${romIdIndex.value[currentRomIndex.value - 1]}`);
  }
}

function nextRom() {
  if (currentRomIndex.value < romIdIndex.value.length - 1) {
    router.push(`/rom/${romIdIndex.value[currentRomIndex.value + 1]}`);
  }
}
</script>

<template>
  <v-card
    v-if="currentRom"
    :key="currentRom.updated_at"
    elevation="0"
    rounded="0"
    class="w-100"
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
    <v-btn-group
      v-if="romIdIndex.length > 1"
      density="compact"
      class="justify-center mb-2 px-2 position-absolute bottom-0 right-0"
      :class="{ 'd-flex justify-space-between w-100': !smAndUp }"
    >
      <v-btn
        size="small"
        density="compact"
        :disabled="currentRomIndex <= 0"
        @click="previousRom"
      >
        <v-icon>mdi-arrow-left</v-icon>
      </v-btn>
      <v-btn
        size="small"
        density="compact"
        :disabled="currentRomIndex === romIdIndex.length - 1"
        @click="nextRom"
      >
        <v-icon>mdi-arrow-right</v-icon>
      </v-btn>
    </v-btn-group>
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
