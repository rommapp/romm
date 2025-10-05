<script setup lang="ts">
import { computed, ref, watchEffect } from "vue";
import Skeleton from "@/components/common/Game/Card/Skeleton.vue";
import { type CollectionType } from "@/stores/collections";
import storeHeartbeat from "@/stores/heartbeat";
import {
  getCollectionCoverImage,
  getFavoriteCoverImage,
  EXTENSION_REGEX,
} from "@/utils/covers";

const props = withDefaults(
  defineProps<{
    collection: CollectionType;
    size?: number;
  }>(),
  {
    size: 45,
  },
);

const heartbeatStore = storeHeartbeat();
const memoizedCovers = ref(["", ""]);

const collectionCoverImage = computed(() =>
  !props.collection.is_virtual && props.collection.is_favorite
    ? getFavoriteCoverImage(props.collection.name)
    : getCollectionCoverImage(props.collection.name),
);

watchEffect(() => {
  // Check if it's a regular collection with covers or a smart collection with covers
  const isRegularOrSmartWithCovers =
    !props.collection.is_virtual && props.collection.path_cover_small;

  const isWebpEnabled =
    heartbeatStore.value.TASKS?.ENABLE_SCHEDULED_CONVERT_IMAGES_TO_WEBP;
  const pathCoverSmall = isWebpEnabled
    ? props.collection.path_cover_small?.replace(EXTENSION_REGEX, ".webp")
    : props.collection.path_cover_small;

  if (isRegularOrSmartWithCovers) {
    memoizedCovers.value = [pathCoverSmall || "", pathCoverSmall || ""];
    return;
  }

  // Handle virtual collections which have plural covers arrays
  const smallCoverUrls = props.collection.path_covers_small.map((url) =>
    isWebpEnabled ? url.replace(EXTENSION_REGEX, ".webp") : url,
  );

  if (smallCoverUrls.length < 2) {
    memoizedCovers.value = [
      collectionCoverImage.value,
      collectionCoverImage.value,
    ];
    return;
  }

  const shuffledSmall = [...smallCoverUrls].sort(() => Math.random() - 0.5);
  memoizedCovers.value = [shuffledSmall[0], shuffledSmall[1]];
});

const firstCover = computed(() => memoizedCovers.value[0]);
const secondCover = computed(() => memoizedCovers.value[1]);
</script>

<template>
  <v-avatar :rounded="0" :size="size">
    <div class="image-container" :style="{ aspectRatio: 1 / 1 }">
      <template v-if="collection.is_virtual || !collection.path_cover_small">
        <div class="split-image first-image">
          <v-img cover :src="firstCover" :aspect-ratio="1 / 1">
            <template #placeholder>
              <Skeleton :aspect-ratio="1 / 1" type="image" />
            </template>
            <template #error>
              <v-img cover :src="collectionCoverImage" :aspect-ratio="1 / 1" />
            </template>
          </v-img>
        </div>
        <div class="split-image second-image">
          <v-img cover :src="secondCover" :aspect-ratio="1 / 1">
            <template #placeholder>
              <Skeleton :aspect-ratio="1 / 1" type="image" />
            </template>
            <template #error>
              <v-img cover :src="collectionCoverImage" :aspect-ratio="1 / 1" />
            </template>
          </v-img>
        </div>
      </template>
      <template v-else>
        <div class="split-image first-image">
          <v-img cover :src="firstCover" :aspect-ratio="1 / 1">
            <template #placeholder>
              <Skeleton :aspect-ratio="1 / 1" type="image" />
            </template>
            <template #error>
              <v-img cover :src="collectionCoverImage" :aspect-ratio="1 / 1" />
            </template>
          </v-img>
        </div>
      </template>
    </div>
  </v-avatar>
</template>

<style scoped>
.image-container {
  position: relative;
  width: 100%;
  overflow: hidden;
}

.split-image {
  position: absolute;
  top: 0;
  width: 100%;
  height: 100%;
}

.first-image {
  clip-path: polygon(0 0, 100% 0, 0% 100%, 0 100%);
  z-index: 1;
}

.second-image {
  clip-path: polygon(0% 100%, 100% 0, 100% 100%);
  z-index: 0;
}
</style>
