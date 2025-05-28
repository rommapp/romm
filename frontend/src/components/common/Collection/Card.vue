<script setup lang="ts">
import type { Collection, VirtualCollection } from "@/stores/collections";
import storeGalleryView from "@/stores/galleryView";
import { ROUTES } from "@/plugins/router";
import { computed, ref, watchEffect, onMounted, onBeforeUnmount } from "vue";
import { useDisplay } from "vuetify";
import VanillaTilt from "vanilla-tilt";
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
    enable3DTilt?: boolean;
    src?: string;
  }>(),
  {
    transformScale: false,
    showTitle: true,
    titleOnHover: false,
    showRomCount: false,
    withLink: false,
    enable3DTilt: false,
    src: "",
  },
);

const { smAndDown } = useDisplay();
const galleryViewStore = storeGalleryView();

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

// Tilt 3D effect logic
interface TiltHTMLElement extends HTMLElement {
  vanillaTilt?: {
    destroy: () => void;
  };
}
const emit = defineEmits(["hover"]);

const tiltCard = ref<TiltHTMLElement | null>(null);

onMounted(() => {
  if (tiltCard.value && !smAndDown.value && props.enable3DTilt) {
    VanillaTilt.init(tiltCard.value, {
      max: 20,
      speed: 400,
      scale: 1.1,
      glare: true,
      "max-glare": 0.3,
    });
  }
});

onBeforeUnmount(() => {
  if (tiltCard.value?.vanillaTilt && props.enable3DTilt) {
    tiltCard.value.vanillaTilt.destroy();
  }
});
</script>

<template>
  <v-hover v-slot="{ isHovering, props: hoverProps }">
    <div data-tilt ref="tiltCard">
      <v-card
        v-bind="{
          ...hoverProps,
          ...(withLink && collection
            ? {
                to: {
                  name: ROUTES.COLLECTION,
                  params: { collection: collection.id },
                },
              }
            : {}),
        }"
        :class="{
          'on-hover': isHovering,
          'transform-scale': transformScale && !enable3DTilt,
        }"
        :elevation="isHovering && transformScale ? 20 : 3"
        :aria-label="`${collection.name} game card`"
        @mouseenter="
          () => {
            emit('hover', { isHovering: true, id: collection.id });
          }
        "
        @mouseleave="
          () => {
            emit('hover', { isHovering: false, id: collection.id });
          }
        "
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
          :style="{
            aspectRatio: galleryViewStore.defaultAspectRatioCollection,
          }"
        >
          <template
            v-if="collection.is_virtual || !collection.path_cover_large"
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
              :src="src || collection.path_cover_large"
              :lazy-src="src || collection.path_cover_small?.toString()"
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
    </div>
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
