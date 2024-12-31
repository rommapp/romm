<script setup lang="ts">
import Collections from "@/components/Home/Collections.vue";
import Platforms from "@/components/Home/Platforms.vue";
import RecentSkeletonLoader from "@/components/Home/RecentSkeletonLoader.vue";
import RecentAdded from "@/components/Home/RecentAdded.vue";
import ContinuePlaying from "@/components/Home/ContinuePlaying.vue";
import Stats from "@/components/Home/Stats.vue";
import romApi from "@/services/api/rom";
import storeCollections from "@/stores/collections";
import storePlatforms from "@/stores/platforms";
import storeRoms from "@/stores/roms";
import { storeToRefs } from "pinia";
import { onMounted, ref } from "vue";
import { isNull } from "lodash";
import { useI18n } from "vue-i18n";

// Props
const { t } = useI18n();
const romsStore = storeRoms();
const { recentRoms, continuePlayingRoms: recentPlayedRoms } =
  storeToRefs(romsStore);
const platforms = storePlatforms();
const { filledPlatforms } = storeToRefs(platforms);
const collections = storeCollections();
const { allCollections } = storeToRefs(collections);
const showRecentRoms = isNull(localStorage.getItem("settings.showRecentRoms"))
  ? true
  : localStorage.getItem("settings.showRecentRoms") === "true";
const showContinuePlaying = isNull(
  localStorage.getItem("settings.showContinuePlaying"),
)
  ? true
  : localStorage.getItem("settings.showContinuePlaying") === "true";
const showPlatforms = isNull(localStorage.getItem("settings.showPlatforms"))
  ? true
  : localStorage.getItem("settings.showPlatforms") === "true";
const showCollections = isNull(localStorage.getItem("settings.showCollections"))
  ? true
  : localStorage.getItem("settings.showCollections") === "true";
const fetchingRecentAdded = ref(false);
const fetchingContinuePlaying = ref(false);

// Functions
onMounted(async () => {
  fetchingRecentAdded.value = true;
  fetchingContinuePlaying.value = true;
  romApi
    .getRecentRoms()
    .then(({ data: recentData }) => {
      romsStore.setRecentRoms(recentData);
    })
    .catch((error) => {
      console.error(error);
    })
    .finally(() => {
      fetchingRecentAdded.value = false;
    });
  romApi
    .getRecentPlayedRoms()
    .then(({ data: recentPlayedData }) => {
      romsStore.setContinuePlayedRoms(
        recentPlayedData.filter((rom) => rom.rom_user.last_played),
      );
    })
    .catch((error) => {
      console.error(error);
    })
    .finally(() => {
      fetchingContinuePlaying.value = false;
    });
});
</script>

<template>
  <stats />
  <recent-skeleton-loader
    v-if="showRecentRoms && fetchingRecentAdded"
    :title="t('home.recently-added')"
  />
  <recent-added
    v-if="recentRoms.length > 0 && showRecentRoms && !fetchingRecentAdded"
  />
  <recent-skeleton-loader
    v-if="showContinuePlaying && fetchingContinuePlaying"
    :title="t('home.continue-playing')"
  />
  <continue-playing
    v-if="
      recentPlayedRoms.length > 0 &&
      showContinuePlaying &&
      !fetchingContinuePlaying
    "
  />
  <platforms v-if="filledPlatforms.length > 0 && showPlatforms" />
  <collections v-if="allCollections.length > 0 && showCollections" />
</template>
