<script setup lang="ts">
import type { VirtualCollection } from "@/stores/collections";
import storeGalleryView from "@/stores/galleryView";
import { useTheme } from "vuetify";
import { computed, ref, watchEffect } from "vue";

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

const memoizedCovers = ref({
  large: ["", ""],
  small: ["", ""],
});

watchEffect(() => {
  const largeCoverUrls = props.collection.path_covers_large || [];
  const smallCoverUrls = props.collection.path_covers_small || [];

  if (largeCoverUrls.length < 2) {
    memoizedCovers.value = {
      large: [
        `/assets/default/cover/big_${theme.global.name.value}_collection.png`,
        `/assets/default/cover/big_${theme.global.name.value}_collection.png`,
      ],
      small: [
        `/assets/default/cover/small_${theme.global.name.value}_collection.png`,
        `/assets/default/cover/small_${theme.global.name.value}_collection.png`,
      ],
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
