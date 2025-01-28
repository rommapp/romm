<script setup lang="ts">
import type { VirtualCollection } from "@/stores/collections";
import storeGalleryView from "@/stores/galleryView";
import { useTheme } from "vuetify";
import { computed } from "vue";

// Props
const props = withDefaults(
  defineProps<{
    collection: VirtualCollection;
    transformScale?: boolean;
    showTitle?: boolean;
    showRomCount?: boolean;
    withLink?: boolean;
  }>(),
  {
    transformScale: false,
    showTitle: false,
    showRomCount: false,
    withLink: false,
  },
);

const theme = useTheme();
const galleryViewStore = storeGalleryView();

const getRandomCovers = computed(() => {
  const largeCoverUrls = props.collection.path_covers_large || [];
  const smallCoverUrls = props.collection.path_covers_small || [];

  // Create a copy of the arrays to avoid mutating the original
  const shuffledLarge = [...largeCoverUrls].sort(() => Math.random() - 0.5);
  const shuffledSmall = [...smallCoverUrls].sort(() => Math.random() - 0.5);

  console.log(shuffledLarge, shuffledSmall);

  return {
    large: [
      shuffledLarge[0] ||
        `/assets/default/cover/big_${theme.global.name.value}_collection.png`,
      shuffledLarge[1] ||
        `/assets/default/cover/big_${theme.global.name.value}_collection.png`,
    ],
    small: [
      shuffledSmall[0] ||
        `/assets/default/cover/small_${theme.global.name.value}_collection.png`,
      shuffledSmall[1] ||
        `/assets/default/cover/small_${theme.global.name.value}_collection.png`,
    ],
  };
});

const firstCover = computed(() => getRandomCovers.value.large[0]);
const secondCover = computed(() => getRandomCovers.value.large[1]);
const firstSmallCover = computed(() => getRandomCovers.value.small[0]);
const secondSmallCover = computed(() => getRandomCovers.value.small[1]);
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
      <v-row v-if="showTitle" class="pa-1 justify-center bg-primary">
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
      </div>

      <v-chip
        v-if="showRomCount"
        class="bg-chip position-absolute"
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

.second-image {
  clip-path: polygon(0% 100%, 100% 0, 100% 100%);
  z-index: 0;
}
</style>
