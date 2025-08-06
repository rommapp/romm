<script setup lang="ts">
import { type CollectionType } from "@/stores/collections";
import storeCollections from "@/stores/collections";
import { getCollectionCoverImage, getFavoriteCoverImage } from "@/utils/covers";
import { computed, ref, watchEffect } from "vue";
import { useTheme } from "vuetify";

const props = withDefaults(
  defineProps<{
    collection: CollectionType;
    size?: number;
  }>(),
  {
    size: 45,
  },
);

const memoizedCovers = ref({
  large: ["", ""],
  small: ["", ""],
  largeWebp: ["", ""],
  smallWebp: ["", ""],
});

const collectionCoverImage = computed(() =>
  !props.collection.is_virtual && props.collection.is_favorite
    ? getFavoriteCoverImage(props.collection.name)
    : getCollectionCoverImage(props.collection.name),
);

watchEffect(() => {
  if (
    !props.collection.is_virtual &&
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
      largeWebp: [
        props.collection.path_cover_large?.split(".").slice(0, -1).join(".") +
          ".webp" || "",
        props.collection.path_cover_large?.split(".").slice(0, -1).join(".") +
          ".webp" || "",
      ],
      smallWebp: [
        props.collection.path_cover_small?.split(".").slice(0, -1).join(".") +
          ".webp" || "",
        props.collection.path_cover_small?.split(".").slice(0, -1).join(".") +
          ".webp" || "",
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
      largeWebp: [
        collectionCoverImage.value.split(".").slice(0, -1).join(".") +
          ".webp" || "",
        collectionCoverImage.value.split(".").slice(0, -1).join(".") +
          ".webp" || "",
      ],
      smallWebp: [
        collectionCoverImage.value.split(".").slice(0, -1).join(".") +
          ".webp" || "",
        collectionCoverImage.value.split(".").slice(0, -1).join(".") +
          ".webp" || "",
      ],
    };
    return;
  }

  const shuffledLarge = [...largeCoverUrls].sort(() => Math.random() - 0.5);
  const shuffledSmall = [...smallCoverUrls].sort(() => Math.random() - 0.5);

  memoizedCovers.value = {
    large: [shuffledLarge[0], shuffledLarge[1]],
    small: [shuffledSmall[0], shuffledSmall[1]],
    largeWebp: [
      shuffledLarge[0].split(".").slice(0, -1).join(".") + ".webp" || "",
      shuffledLarge[1].split(".").slice(0, -1).join(".") + ".webp" || "",
    ],
    smallWebp: [
      shuffledSmall[0].split(".").slice(0, -1).join(".") + ".webp" || "",
      shuffledSmall[1].split(".").slice(0, -1).join(".") + ".webp" || "",
    ],
  };
});

const firstLargeCover = computed(() => memoizedCovers.value.large[0]);
const secondLargeCover = computed(() => memoizedCovers.value.large[1]);
const firstSmallCover = computed(() => memoizedCovers.value.small[0]);
const secondSmallCover = computed(() => memoizedCovers.value.small[1]);
const firstLargeWebpCover = computed(() => memoizedCovers.value.largeWebp[0]);
const secondLargeWebpCover = computed(() => memoizedCovers.value.largeWebp[1]);
const firstSmallWebpCover = computed(() => memoizedCovers.value.smallWebp[0]);
const secondSmallWebpCover = computed(() => memoizedCovers.value.smallWebp[1]);
</script>

<template>
  <v-avatar :rounded="0" :size="size">
    <div class="image-container" :style="{ aspectRatio: 1 / 1 }">
      <template
        v-if="
          collection.is_virtual ||
          !collection.path_cover_large ||
          !collection.path_cover_small
        "
      >
        <div class="split-image first-image">
          <v-img
            cover
            :lazy-src="firstSmallWebpCover"
            :src="firstLargeWebpCover"
            :aspect-ratio="1 / 1"
          >
            <template #error>
              <v-img :lazy-src="firstSmallCover" :src="firstLargeCover" />
            </template>
          </v-img>
        </div>
        <div class="split-image second-image">
          <v-img
            cover
            :lazy-src="secondSmallWebpCover"
            :src="secondLargeWebpCover"
            :aspect-ratio="1 / 1"
          >
            <template #error>
              <v-img :lazy-src="secondSmallCover" :src="secondLargeCover" />
            </template>
          </v-img>
        </div>
      </template>
      <template v-else>
        <v-img
          cover
          :lazy-src="firstSmallWebpCover"
          :src="firstLargeWebpCover"
          :aspect-ratio="1 / 1"
        />
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
