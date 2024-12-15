<script setup lang="ts">
import Collections from "@/components/Home/Collections.vue";
import Platforms from "@/components/Home/Platforms.vue";
import RecentlyAdded from "@/components/Home/Recent.vue";
import Stats from "@/components/Home/Stats.vue";
import romApi from "@/services/api/rom";
import storeCollections from "@/stores/collections";
import storePlatforms from "@/stores/platforms";
import storeRoms from "@/stores/roms";
import { storeToRefs } from "pinia";
import { onMounted } from "vue";
import { isNull } from "lodash";

// Props
const romsStore = storeRoms();
const { recentRoms } = storeToRefs(romsStore);
const platforms = storePlatforms();
const { filledPlatforms } = storeToRefs(platforms);
const collections = storeCollections();
const { allCollections } = storeToRefs(collections);
const showRecentRoms = isNull(localStorage.getItem("settings.showRecentRoms"))
  ? true
  : localStorage.getItem("settings.showRecentRoms") === "true";
const showPlatforms = isNull(localStorage.getItem("settings.showPlatforms"))
  ? true
  : localStorage.getItem("settings.showPlatforms") === "true";
const showCollections = isNull(localStorage.getItem("settings.showCollections"))
  ? true
  : localStorage.getItem("settings.showCollections") === "true";

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
  <recently-added v-if="recentRoms.length > 0 && showRecentRoms" />
  <platforms v-if="filledPlatforms.length > 0 && showPlatforms" />
  <collections v-if="allCollections.length > 0 && showCollections" />
</template>
