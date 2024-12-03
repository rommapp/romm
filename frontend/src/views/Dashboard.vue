<script setup lang="ts">
import Collections from "@/components/Dashboard/Collections.vue";
import Platforms from "@/components/Dashboard/Platforms.vue";
import recentlyAdded from "@/components/Dashboard/Recent.vue";
import Stats from "@/components/Dashboard/Stats.vue";
import romApi from "@/services/api/rom";
import storeCollections from "@/stores/collections";
import storePlatforms from "@/stores/platforms";
import storeRoms from "@/stores/roms";
import { storeToRefs } from "pinia";
import { onMounted } from "vue";

// Props
const romsStore = storeRoms();
const { recentRoms } = storeToRefs(romsStore);
const platforms = storePlatforms();
const { filledPlatforms } = storeToRefs(platforms);
const collections = storeCollections();
const { allCollections } = storeToRefs(collections);

// Functions
onMounted(async () => {
  await romApi
    .getRecentRoms()
    .then(({ data: recentData }) => {
      romsStore.setRecentRoms(recentData);
    })
    .catch((error) => {
      console.error(error);
    });
});
</script>

<template>
  <stats />
  <recently-added v-if="recentRoms.length > 0" />
  <platforms v-if="filledPlatforms.length > 0" />
  <collections v-if="allCollections.length > 0" />
</template>
