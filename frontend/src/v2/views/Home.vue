<script setup lang="ts">
// Home dashboard — composed of primitives + feature components. Each
// section is a CardRow with its own tile type in the default slot.
//
// Gamepad / keyboard arrow navigation: the root is registered with
// `useGridNav`, which treats each CardRow track as a row and its children
// as cells. When the input modality flips to `"pad"` (gamepad detected
// or pressed) we autofocus the first cell so the synthetic keys
// dispatched by `useGamepad` have somewhere to go.
import { RIcon, RSkeletonBlock } from "@v2/lib";
import { storeToRefs } from "pinia";
import { computed, onMounted, ref } from "vue";
import storeCollections from "@/stores/collections";
import storePlatforms from "@/stores/platforms";
import storeRoms, { type SimpleRom } from "@/stores/roms";
import CollectionTile from "@/v2/components/Collections/CollectionTile.vue";
import { GameCard, GameCardSkeleton } from "@/v2/components/GameCard";
import CardRow from "@/v2/components/Home/CardRow.vue";
import PlatformTile from "@/v2/components/Platforms/PlatformTile.vue";
import { useGridNav } from "@/v2/composables/useGridNav";
import { useWebpSupport } from "@/v2/composables/useWebpSupport";

const romsStore = storeRoms();
const platformsStore = storePlatforms();
const collectionsStore = storeCollections();
const { supportsWebp, toWebp } = useWebpSupport();

const { recentRoms, continuePlayingRoms } = storeToRefs(romsStore);
const { filledPlatforms, fetchingPlatforms } = storeToRefs(platformsStore);
const { allCollections, favoriteCollection, fetchingCollections } =
  storeToRefs(collectionsStore);

const fetchingRecent = ref(false);
const fetchingContinue = ref(false);

const gridRoot = ref<HTMLElement | null>(null);
useGridNav(gridRoot);

onMounted(() => {
  if (platformsStore.allPlatforms.length === 0) {
    platformsStore.fetchPlatforms();
  }
  if (collectionsStore.allCollections.length === 0) {
    collectionsStore.fetchCollections();
  }
  if (recentRoms.value.length === 0) {
    fetchingRecent.value = true;
    romsStore.fetchRecentRoms().finally(() => (fetchingRecent.value = false));
  }
  if (continuePlayingRoms.value.length === 0) {
    fetchingContinue.value = true;
    romsStore
      .fetchContinuePlayingRoms()
      .finally(() => (fetchingContinue.value = false));
  }
});

// Favorite ROMs — derived from the Favorites collection's rom_ids.
// eslint-disable-next-line @typescript-eslint/no-unused-vars -- false positive: used in <template>; @typescript-eslint+projectService doesn't see Vue templates
const favoriteRoms = computed<SimpleRom[]>(() => {
  const favIds = favoriteCollection.value?.rom_ids ?? [];
  if (!favIds.length) return [];
  const pool = new Map<number, SimpleRom>();
  for (const r of recentRoms.value) pool.set(r.id, r);
  for (const r of continuePlayingRoms.value) pool.set(r.id, r);
  const out: SimpleRom[] = [];
  for (const id of favIds) {
    const hit = pool.get(id);
    if (hit) out.push(hit);
  }
  return out;
});

// Pick a small set of cover URLs to seed the collection tile mosaic.
function collectionCovers(pathCovers: string[] | undefined): string[] {
  return (pathCovers ?? []).slice(0, 4).map(toWebp);
}
</script>

<template>
  <div ref="gridRoot" class="r-v2-home">
    <!-- Continue playing -->
    <CardRow
      v-if="continuePlayingRoms.length || fetchingContinue"
      title="Continue playing"
      :count="continuePlayingRoms.length"
    >
      <template #icon>
        <RIcon icon="mdi-play" size="20" />
      </template>
      <template v-if="fetchingContinue && !continuePlayingRoms.length">
        <GameCardSkeleton v-for="n in 4" :key="`cs-${n}`" hero />
      </template>
      <template v-else>
        <GameCard
          v-for="rom in continuePlayingRoms"
          :key="`cont-${rom.id}`"
          :rom="rom"
          :webp="supportsWebp"
          hero
        />
      </template>
    </CardRow>

    <!-- Recently added -->
    <CardRow title="Recently added" :count="recentRoms.length">
      <template #icon>
        <RIcon icon="mdi-shimmer" size="20" />
      </template>
      <template v-if="fetchingRecent && !recentRoms.length">
        <GameCardSkeleton v-for="n in 6" :key="`rs-${n}`" />
      </template>
      <div v-else-if="!recentRoms.length" class="r-v2-home__empty">
        No games added yet.
      </div>
      <template v-else>
        <GameCard
          v-for="rom in recentRoms"
          :key="`rec-${rom.id}`"
          :rom="rom"
          :webp="supportsWebp"
        />
      </template>
    </CardRow>

    <!-- Favorites -->
    <!-- <CardRow
      v-if="favoriteRoms.length"
      title="Favorites"
      :count="favoriteRoms.length"
    >
      <template #icon>
        <RIcon icon="mdi-heart" size="20" />
      </template>
      <GameCard
        v-for="rom in favoriteRoms"
        :key="`fav-${rom.id}`"
        :rom="rom"
        :webp="supportsWebp"
      />
    </CardRow> -->

    <!-- Platforms -->
    <CardRow title="Platforms" :count="filledPlatforms.length" gap="16px">
      <template #icon>
        <RIcon icon="mdi-controller" size="20" />
      </template>
      <template v-if="fetchingPlatforms && !filledPlatforms.length">
        <RSkeletonBlock
          v-for="n in 8"
          :key="`ps-${n}`"
          width="150px"
          height="140px"
          rounded="card"
        />
      </template>
      <PlatformTile
        v-for="p in filledPlatforms"
        v-else
        :key="`plat-${p.id}`"
        :id="p.id"
        :slug="p.slug"
        :fs-slug="p.fs_slug"
        :display-name="p.display_name"
        :rom-count="p.rom_count"
        variant="row"
      />
    </CardRow>

    <!-- Collections -->
    <CardRow
      v-if="allCollections.length || fetchingCollections"
      title="Collections"
      :count="allCollections.length"
      gap="16px"
    >
      <template #icon>
        <RIcon icon="mdi-bookmark-outline" size="20" />
      </template>
      <CollectionTile
        v-for="c in allCollections"
        :id="c.id"
        :key="`coll-${c.id}`"
        :to="`/collection/${c.id}`"
        :name="c.name"
        :rom-count="c.rom_count"
        :covers="collectionCovers(c.path_covers_small ?? [])"
        variant="row"
      />
    </CardRow>
  </div>
</template>

<style scoped>
.r-v2-home {
  padding: 16px 0 48px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.r-v2-home__empty {
  color: var(--r-color-fg-faint);
  font-size: 13px;
  padding: 24px var(--r-row-pad);
}
</style>
