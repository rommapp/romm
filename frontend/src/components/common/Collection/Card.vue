<script setup lang="ts">
import type { Collection, VirtualCollection } from "@/stores/collections";
import storeGalleryView from "@/stores/galleryView";
import storeCollections from "@/stores/collections";
import { computed, ref, watchEffect } from "vue";
import { getCollectionCoverImage, getFavoriteCoverImage } from "@/utils/covers";

// Props
const props = withDefaults(
  defineProps<{
    collection: Collection | VirtualCollection;
    transformScale?: boolean;
    showTitle?: boolean;
    titleOnHover?: boolean;
    showRomCount?: boolean;
    withLink?: boolean;
    src?: string;
  }>(),
  {
    transformScale: false,
    showTitle: true,
    titleOnHover: false,
    showRomCount: false,
    withLink: false,
    src: "",
  },
);

const galleryViewStore = storeGalleryView();
const collectionsStore = storeCollections();

const memoizedCovers = ref({
  large: ["", ""],
  small: ["", ""],
});

const collectionCoverImage = computed(() =>
  props.collection.name?.toLowerCase() == "favourites"
    ? getFavoriteCoverImage(props.collection.name)
    : getCollectionCoverImage(props.collection.name),
);

watchEffect(() => {
  if (props.src) {
    memoizedCovers.value = {
      large: [props.src, props.src],
      small: [props.src, props.src],
    };
    return;
  }

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
  <v-hover v-slot="{ isHovering, props: hoverProps }">
    <v-card
      v-bind="{
        ...hoverProps,
        ...(withLink && collection
          ? {
              to: { name: 'collection', params: { collection: collection.id } },
            }
          : {}),
      }"
      :class="{
        'on-hover': isHovering,
        'transform-scale': transformScale,
      }"
      :elevation="isHovering && transformScale ? 20 : 3"
    >
      <v-row v-if="showTitle" class="pa-1 justify-center bg-surface">
        <div
          :title="collection.name?.toString()"
          class="py-4 px-6 text-truncate text-caption"
        >
          <span>{{ collection.name }}</span>
        </div>
      </v-row>
      <div
        class="image-container"
        :style="{ aspectRatio: galleryViewStore.defaultAspectRatioCollection }"
      >
        <template
          v-if="
            collectionsStore.isVirtualCollection(collection) ||
            !collection.path_cover_large
          "
        >
          <div class="split-image first-image">
            <v-img
              cover
              :src="firstCover"
              :lazy-src="firstSmallCover"
              :aspect-ratio="galleryViewStore.defaultAspectRatioCollection"
            />
          </div>
          <div class="split-image second-image">
            <v-img
              cover
              :src="secondCover"
              :lazy-src="secondSmallCover"
              :aspect-ratio="galleryViewStore.defaultAspectRatioCollection"
            />
          </div>
        </template>
        <template v-else>
          <v-img
            cover
            :src="collection.path_cover_large"
            :lazy-src="collection.path_cover_small?.toString()"
            :aspect-ratio="galleryViewStore.defaultAspectRatioCollection"
          />
        </template>
        <div class="position-absolute append-inner">
          <slot name="append-inner"></slot>
        </div>
      </div>
      <v-chip
        v-if="showRomCount"
        class="bg-background position-absolute"
        size="x-small"
        style="bottom: 0.5rem; right: 0.5rem"
        label
      >
        {{ collection.rom_count }}
      </v-chip>
    </v-card>
  </v-hover>
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

.append-inner {
  bottom: 0rem;
  right: 0rem;
}
</style>
