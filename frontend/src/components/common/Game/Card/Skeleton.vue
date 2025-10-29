<script setup lang="ts">
import { computed } from "vue";
import { useDisplay } from "vuetify";
import storeGalleryView from "@/stores/galleryView";
import storePlatforms from "@/stores/platforms";

const props = withDefaults(
  defineProps<{
    platformId?: number;
    aspectRatio?: string | number;
    type?: string;
  }>(),
  {
    platformId: undefined,
    aspectRatio: undefined,
    type: undefined,
  },
);

const { smAndDown } = useDisplay();
const platformsStore = storePlatforms();
const galleryViewStore = storeGalleryView();

const computedAspectRatio = computed(() => {
  const ratio =
    props.aspectRatio ||
    platformsStore.getAspectRatio(props.platformId || 0) ||
    galleryViewStore.defaultAspectRatioCover;
  return parseFloat(ratio.toString());
});

const computedType = computed(() => {
  if (props.type) return props.type;
  return "image, avatar, chip, chip";
});
</script>

<template>
  <v-skeleton-loader
    class="card-skeleton"
    :type="computedType"
    :style="{ aspectRatio: computedAspectRatio }"
  />
</template>

<style>
.card-skeleton {
  border-radius: 4px;
}

.card-skeleton .v-skeleton-loader__card-avatar {
  height: 100%;
}

.card-skeleton .v-skeleton-loader__image {
  height: 100%;
  border-radius: 4px;
}

.card-skeleton .v-skeleton-loader__avatar {
  position: absolute;
  bottom: 0;
  left: 0;

  margin: 4px;
  min-height: 32px;
  min-width: 32px;
  max-height: 32px;
  max-width: 32px;

  &:after {
    animation: none;
  }
}

.card-skeleton .v-skeleton-loader__chip {
  position: absolute;
  font-size: 0.875rem;
  padding: 0 12px;
  height: 24px;
  margin: 4px;
  margin-inline-start: 4px !important;

  &:after {
    animation: none;
  }
}

.card-skeleton .v-skeleton-loader__chip:nth-of-type(3) {
  bottom: 0;
  right: 4px;
}

.card-skeleton .v-skeleton-loader__chip:nth-of-type(4) {
  top: 0;
  left: 0;
}

.card-skeleton .v-skeleton-loader__actions {
  display: none;
}
</style>
