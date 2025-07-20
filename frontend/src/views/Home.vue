<script setup lang="ts">
import { onMounted, ref, computed } from "vue";
import { storeToRefs } from "pinia";
import { useI18n } from "vue-i18n";
import Stats from "@/components/Home/Stats.vue";
import Collections from "@/components/Home/Collections.vue";
import VirtualCollections from "@/components/Home/VirtualCollections.vue";
import Platforms from "@/components/Home/Platforms.vue";
import RecentSkeletonLoader from "@/components/Home/RecentSkeletonLoader.vue";
import RecentAdded from "@/components/Home/RecentAdded.vue";
import ContinuePlaying from "@/components/Home/ContinuePlaying.vue";
import EmptyHome from "@/components/Home/EmptyHome.vue";
import romApi from "@/services/api/rom";
import storeCollections from "@/stores/collections";
import storePlatforms from "@/stores/platforms";
import storeRoms from "@/stores/roms";

const { t } = useI18n();
const romsStore = storeRoms();
const { recentRoms, continuePlayingRoms: recentPlayedRoms } =
  storeToRefs(romsStore);
const platformsStore = storePlatforms();
const { filledPlatforms } = storeToRefs(platformsStore);
const collectionsStore = storeCollections();
const { allCollections, virtualCollections } = storeToRefs(collectionsStore);

function getSettingValue(key: string, defaultValue: boolean = true): boolean {
  const stored = localStorage.getItem(`settings.${key}`);
  return stored === null ? defaultValue : stored === "true";
}

const showStats = getSettingValue("showStats");
const showRecentRoms = getSettingValue("showRecentRoms");
const showContinuePlaying = getSettingValue("showContinuePlaying");
const showPlatforms = getSettingValue("showPlatforms");
const showCollections = getSettingValue("showCollections");
const showVirtualCollections = getSettingValue("showVirtualCollections");

const fetchingRecentAdded = ref(false);
const fetchingContinuePlaying = ref(false);

const isEmpty = computed(
  () =>
    recentRoms.value.length === 0 &&
    recentPlayedRoms.value.length === 0 &&
    filledPlatforms.value.length === 0 &&
    allCollections.value.length === 0 &&
    virtualCollections.value.length === 0,
);

const showRecentSkeleton = computed(
  () =>
    showRecentRoms &&
    fetchingRecentAdded.value &&
    recentRoms.value.length === 0,
);

const showContinuePlayingSkeleton = computed(
  () =>
    showContinuePlaying &&
    fetchingContinuePlaying.value &&
    recentPlayedRoms.value.length === 0,
);

const fetchRecentRoms = async (): Promise<void> => {
  try {
    fetchingRecentAdded.value = true;
    const {
      data: { items },
    } = await romApi.getRecentRoms();
    romsStore.setRecentRoms(items);
  } catch (error) {
    console.error("Failed to fetch recent ROMs:", error);
  } finally {
    fetchingRecentAdded.value = false;
  }
};

const fetchContinuePlayingRoms = async (): Promise<void> => {
  try {
    fetchingContinuePlaying.value = true;
    const {
      data: { items },
    } = await romApi.getRecentPlayedRoms();
    const filteredItems = items.filter((rom) => rom.rom_user.last_played);
    romsStore.setContinuePlayingRoms(filteredItems);
  } catch (error) {
    console.error("Failed to fetch continue playing ROMs:", error);
  } finally {
    fetchingContinuePlaying.value = false;
  }
};

onMounted(async () => {
  await Promise.all([fetchRecentRoms(), fetchContinuePlayingRoms()]);
});
</script>

<template>
  <template v-if="!isEmpty">
    <stats v-if="showStats" />
    <recent-skeleton-loader
      v-if="showRecentSkeleton"
      :title="t('home.recently-added')"
      class="ma-2"
    />
    <recent-added
      v-else-if="recentRoms.length > 0 && showRecentRoms"
      class="ma-2"
    />
    <recent-skeleton-loader
      v-if="showContinuePlayingSkeleton"
      :title="t('home.continue-playing')"
      class="ma-2"
    />
    <continue-playing
      v-else-if="recentPlayedRoms.length > 0 && showContinuePlaying"
      class="ma-2"
    />
    <platforms
      v-if="filledPlatforms.length > 0 && showPlatforms"
      class="ma-2"
    />
    <collections
      v-if="allCollections.length > 0 && showCollections"
      class="ma-2"
    />
    <virtual-collections
      v-if="virtualCollections.length > 0 && showVirtualCollections"
      class="ma-2"
    />
  </template>
  <empty-home v-else />
</template>
