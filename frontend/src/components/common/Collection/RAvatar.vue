<script setup lang="ts">
import type { Collection, VirtualCollection } from "@/stores/collections";
import storeCollections from "@/stores/collections";
import { getCollectionCoverImage, getFavoriteCoverImage } from "@/utils/covers";
import { computed, ref, watchEffect } from "vue";
import { useTheme } from "vuetify";

const props = withDefaults(
  defineProps<{ collection: Collection | VirtualCollection; size?: number }>(),
  {
    size: 45,
  },
);
const theme = useTheme();
const collectionsStore = storeCollections();

const memoizedCovers = ref({
  large: ["", ""],
  small: ["", ""],
});

const collectionCoverImage = computed(() =>
  !collectionsStore.isVirtualCollection(props.collection) &&
  props.collection.is_favorite
    ? getFavoriteCoverImage(props.collection.name)
    : getCollectionCoverImage(props.collection.name),
);

watchEffect(() => {
  if (
    !collectionsStore.isVirtualCollection(props.collection) &&
    props.collection.path_cover_large &&
    props.collection.path_cover_small
  ) {
    memoizedCovers.value = {
      large: [
        props.collection.path_cover_large,
        props.collection.path_cover_large,
      ],
      small: [
        props.collection.path_cover_small,
        props.collection.path_cover_small,
      ],
    };
    return;
  }

  const largeCoverUrls = props.collection.path_covers_large || [];
  const smallCoverUrls = props.collection.path_covers_small || [];

  if (largeCoverUrls.length < 2) {
    memoizedCovers.value = {
      large: [collectionCoverImage.value, collectionCoverImage.value],
      small: [collectionCoverImage.value, collectionCoverImage.value],
    };
    return;
  }

  const shuffledLarge = [...largeCoverUrls].sort(() => Math.random() - 0.5);
  const shuffledSmall = [...smallCoverUrls].sort(() => Math.random() - 0.5);

  memoizedCovers.value = {
    large: [shuffledLarge[0], shuffledLarge[1]],
    small: [shuffledSmall[0], shuffledSmall[1]],
  };
});

const firstCover = computed(() => memoizedCovers.value.large[0]);
const secondCover = computed(() => memoizedCovers.value.large[1]);
const firstSmallCover = computed(() => memoizedCovers.value.small[0]);
const secondSmallCover = computed(() => memoizedCovers.value.small[1]);
</script>

<template>
  <v-avatar :rounded="0" :size="size">
    <div class="image-container" :style="{ aspectRatio: 1 / 1 }">
      <div class="split-image first-image">
        <v-img
          cover
          :src="firstCover"
          :lazy-src="firstSmallCover"
          :aspect-ratio="1 / 1"
        />
      </div>
      <div class="split-image second-image">
        <v-img
          cover
          :src="secondCover"
          :lazy-src="secondSmallCover"
          :aspect-ratio="1 / 1"
        />
      </div>
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
