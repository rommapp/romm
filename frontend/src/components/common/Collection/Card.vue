<script setup lang="ts">
import VanillaTilt from "vanilla-tilt";
import {
  computed,
  ref,
  watchEffect,
  onMounted,
  onBeforeUnmount,
  useTemplateRef,
} from "vue";
import { useDisplay } from "vuetify";
import Skeleton from "@/components/common/Game/Card/Skeleton.vue";
import { ROUTES } from "@/plugins/router";
import type { CollectionType } from "@/stores/collections";
import storeGalleryView from "@/stores/galleryView";
import storeHeartbeat from "@/stores/heartbeat";
import {
  getCollectionCoverImage,
  getFavoriteCoverImage,
  EXTENSION_REGEX,
} from "@/utils/covers";

const props = withDefaults(
  defineProps<{
    collection: CollectionType;
    coverSrc?: string;
    transformScale?: boolean;
    showTitle?: boolean;
    titleOnHover?: boolean;
    showRomCount?: boolean;
    withLink?: boolean;
    enable3DTilt?: boolean;
  }>(),
  {
    coverSrc: undefined,
    transformScale: false,
    showTitle: true,
    titleOnHover: false,
    showRomCount: false,
    withLink: false,
    enable3DTilt: false,
  },
);

const { smAndDown } = useDisplay();
const heartbeatStore = storeHeartbeat();
const galleryViewStore = storeGalleryView();

const computedAspectRatio = computed(() =>
  galleryViewStore.getAspectRatio({ boxartStyle: "cover_path" }),
);

const memoizedCovers = ref({
  large: ["", ""],
  small: ["", ""],
});

const collectionCoverImage = computed(() =>
  props.collection.is_favorite
    ? getFavoriteCoverImage(props.collection.name)
    : getCollectionCoverImage(props.collection.name),
);

watchEffect(() => {
  if (props.coverSrc) {
    memoizedCovers.value = {
      large: [props.coverSrc, props.coverSrc],
      small: [props.coverSrc, props.coverSrc],
    };
    return;
  }

  // Check if it's a regular collection with covers or a smart collection with covers
  const isRegularOrSmartWithCovers =
    !props.collection.is_virtual &&
    props.collection.path_cover_large &&
    props.collection.path_cover_small;

  const isWebpEnabled =
    heartbeatStore.value.TASKS?.ENABLE_SCHEDULED_CONVERT_IMAGES_TO_WEBP;
  const pathCoverLarge = isWebpEnabled
    ? props.collection.path_cover_large?.replace(EXTENSION_REGEX, ".webp")
    : props.collection.path_cover_large;
  const pathCoverSmall = isWebpEnabled
    ? props.collection.path_cover_small?.replace(EXTENSION_REGEX, ".webp")
    : props.collection.path_cover_small;

  if (isRegularOrSmartWithCovers) {
    memoizedCovers.value = {
      large: [pathCoverLarge || "", pathCoverLarge || ""],
      small: [pathCoverSmall || "", pathCoverSmall || ""],
    };
    return;
  }

  // Handle virtual collections which have plural covers arrays
  const largeCoverUrls = props.collection.path_covers_large.map((url) =>
    isWebpEnabled ? url.replace(EXTENSION_REGEX, ".webp") : url,
  );
  const smallCoverUrls = props.collection.path_covers_small.map((url) =>
    isWebpEnabled ? url.replace(EXTENSION_REGEX, ".webp") : url,
  );

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

const firstLargeCover = computed(() => memoizedCovers.value.large[0]);
const secondLargeCover = computed(() => memoizedCovers.value.large[1]);
const firstSmallCover = computed(() => memoizedCovers.value.small[0]);
const secondSmallCover = computed(() => memoizedCovers.value.small[1]);

// Tilt 3D effect logic
interface TiltHTMLElement extends HTMLElement {
  vanillaTilt?: {
    destroy: () => void;
  };
}
const emit = defineEmits(["hover"]);

const tiltCardRef = useTemplateRef<TiltHTMLElement>("tilt-card-ref");

// Determine the correct route for this collection type
const collectionRoute = computed(() => {
  if (!props.withLink || !props.collection) return {};

  // Check if it's a smart collection (has filter_criteria property)
  if ("filter_criteria" in props.collection) {
    return {
      name: ROUTES.SMART_COLLECTION,
      params: { collection: props.collection.id },
    };
  }

  // Check if it's a virtual collection (has type property)
  if ("type" in props.collection) {
    return {
      name: ROUTES.VIRTUAL_COLLECTION,
      params: { collection: props.collection.id },
    };
  }

  // Default to regular collection route
  return {
    name: ROUTES.COLLECTION,
    params: { collection: props.collection.id },
  };
});

onMounted(() => {
  if (tiltCardRef.value && !smAndDown.value && props.enable3DTilt) {
    VanillaTilt.init(tiltCardRef.value, {
      max: 20,
      speed: 400,
      scale: 1.1,
      glare: true,
      "max-glare": 0.3,
    });
  }
});

onBeforeUnmount(() => {
  if (tiltCardRef.value?.vanillaTilt && props.enable3DTilt) {
    tiltCardRef.value.vanillaTilt.destroy();
  }
});
</script>

<template>
  <div ref="tilt-card-ref" data-tilt>
    <v-card
      v-bind="{
        to: collectionRoute,
      }"
      :class="{
        'transform-scale': transformScale && !enable3DTilt,
      }"
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
      @blur="
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
        :style="{ aspectRatio: computedAspectRatio }"
      >
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
              :src="firstLargeCover"
              :aspect-ratio="computedAspectRatio"
            >
              <template #placeholder>
                <v-img
                  :src="firstSmallCover"
                  :aspect-ratio="computedAspectRatio"
                >
                  <template #placeholder>
                    <Skeleton
                      :aspect-ratio="computedAspectRatio"
                      type="image"
                    />
                  </template>
                </v-img>
              </template>
              <template #error>
                <v-img
                  :src="collectionCoverImage"
                  :aspect-ratio="computedAspectRatio"
                />
              </template>
            </v-img>
          </div>
          <div class="split-image second-image">
            <v-img
              cover
              :src="secondLargeCover"
              :aspect-ratio="computedAspectRatio"
            >
              <template #placeholder>
                <v-img
                  :src="secondSmallCover"
                  :aspect-ratio="computedAspectRatio"
                >
                  <template #placeholder>
                    <Skeleton
                      :aspect-ratio="computedAspectRatio"
                      type="image"
                    />
                  </template>
                </v-img>
              </template>
              <template #error>
                <v-img
                  :src="collectionCoverImage"
                  :aspect-ratio="computedAspectRatio"
                />
              </template>
            </v-img>
          </div>
        </template>
        <template v-else>
          <v-img
            cover
            :src="firstLargeCover"
            :aspect-ratio="computedAspectRatio"
          >
            <template #placeholder>
              <v-img :src="firstSmallCover" :aspect-ratio="computedAspectRatio">
                <template #placeholder>
                  <Skeleton :aspect-ratio="computedAspectRatio" type="image" />
                </template>
              </v-img>
            </template>
            <template #error>
              <v-img
                :src="collectionCoverImage"
                :aspect-ratio="computedAspectRatio"
              />
            </template>
          </v-img>
        </template>
        <div class="position-absolute append-inner">
          <slot name="append-inner" />
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
