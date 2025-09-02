<script setup lang="ts">
import Collections from "@/components/Home/Collections.vue";
import ContinuePlaying from "@/components/Home/ContinuePlaying.vue";
import EmptyHome from "@/components/Home/EmptyHome.vue";
import Platforms from "@/components/Home/Platforms.vue";
import PlatformsSkeleton from "@/components/Home/PlatformsSkeleton.vue";
import RecentAdded from "@/components/Home/RecentAdded.vue";
import RecentAddedSkeleton from "@/components/Home/RecentAddedSkeleton.vue";
import Stats from "@/components/Home/Stats.vue";
import storeCollections from "@/stores/collections";
import storePlatforms from "@/stores/platforms";
import storeRoms from "@/stores/roms";
import { storeToRefs } from "pinia";
import { onBeforeMount, ref, computed } from "vue";
import { useI18n } from "vue-i18n";

const { t } = useI18n();
const romsStore = storeRoms();
const { recentRoms, continuePlayingRoms } = storeToRefs(romsStore);
const platformsStore = storePlatforms();
const { filledPlatforms, fetchingPlatforms } = storeToRefs(platformsStore);
const collectionsStore = storeCollections();
const {
  filteredCollections,
  filteredVirtualCollections,
  filteredSmartCollections,
  fetchingCollections,
  fetchingSmartCollections,
  fetchingVirtualCollections,
} = storeToRefs(collectionsStore);

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
const showSmartCollections = getSettingValue("showSmartCollections");

const fetchingRecentAdded = ref(false);
const fetchingContinuePlaying = ref(false);

const isEmpty = computed(
  () =>
    !fetchingPlatforms.value &&
    !fetchingCollections.value &&
    !fetchingSmartCollections.value &&
    !fetchingVirtualCollections.value &&
    !fetchingRecentAdded.value &&
    !fetchingContinuePlaying.value &&
    recentRoms.value.length === 0 &&
    continuePlayingRoms.value.length === 0 &&
    filledPlatforms.value.length === 0 &&
    filteredCollections.value.length === 0 &&
    filteredVirtualCollections.value.length === 0 &&
    filteredSmartCollections.value.length === 0,
);

onBeforeMount(async () => {
  fetchingRecentAdded.value = true;
  fetchingContinuePlaying.value = true;

  await Promise.all([
    romsStore.fetchRecentRoms(),
    romsStore.fetchContinuePlayingRoms(),
  ]);

  fetchingRecentAdded.value = false;
  fetchingContinuePlaying.value = false;
});
</script>

<template>
  <empty-home v-if="isEmpty" />
  <template v-else>
    <stats v-if="showStats" />

    <template v-if="showRecentRoms">
      <recent-added-skeleton
        v-if="fetchingRecentAdded && recentRoms.length === 0"
        :title="t('home.recently-added')"
        class="ma-2"
      />
      <recent-added v-else-if="recentRoms.length > 0" class="ma-2" />
    </template>

    <template v-if="showContinuePlaying">
      <recent-added-skeleton
        v-if="fetchingContinuePlaying && continuePlayingRoms.length === 0"
        :title="t('home.continue-playing')"
        class="ma-2"
      />
      <continue-playing
        v-else-if="continuePlayingRoms.length > 0"
        class="ma-2"
      />
    </template>

    <template v-if="showPlatforms">
      <platforms-skeleton
        v-if="fetchingPlatforms && filledPlatforms.length === 0"
      />
      <platforms v-else-if="filledPlatforms.length > 0" class="ma-2" />
    </template>

    <template v-if="showCollections">
      <recent-added-skeleton
        v-if="fetchingCollections && filteredCollections.length === 0"
        :title="t('common.collections')"
        class="ma-2"
      />
      <collections
        v-if="filteredCollections.length > 0"
        :collections="filteredCollections"
        :title="t('common.collections')"
        setting="gridCollections"
        class="ma-2"
      />
    </template>

    <template v-if="showSmartCollections">
      <recent-added-skeleton
        v-if="fetchingSmartCollections && filteredSmartCollections.length === 0"
        :title="t('common.smart-collections')"
        class="ma-2"
      />
      <collections
        v-if="filteredSmartCollections.length > 0"
        :collections="filteredSmartCollections"
        :title="t('common.smart-collections')"
        setting="gridSmartCollections"
        class="ma-2"
      />
    </template>

    <template v-if="showVirtualCollections">
      <recent-added-skeleton
        v-if="
          fetchingVirtualCollections && filteredVirtualCollections.length === 0
        "
        :title="t('common.virtual-collections')"
        class="ma-2"
      />
      <collections
        v-if="filteredVirtualCollections.length > 0"
        :collections="filteredVirtualCollections"
        :title="t('common.virtual-collections')"
        setting="gridVirtualCollections"
        class="ma-2"
      />
    </template>
  </template>
</template>
