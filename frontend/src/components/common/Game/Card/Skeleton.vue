<script setup lang="ts">
import storePlatforms from "@/stores/platforms";
import storeGalleryView from "@/stores/galleryView";
import { computed } from "vue";
import { useDisplay } from "vuetify";
import { isNull } from "lodash";

const props = withDefaults(
  defineProps<{
    platformId?: number;
    aspectRatio?: string | number;
    type?: string;
  }>(),
  {
    platformId: undefined,
    aspectRatio: undefined,
    type: "image, avatar, chip, chip, actions",
  },
);

const { smAndDown } = useDisplay();
const platformsStore = storePlatforms();
const galleryViewStore = storeGalleryView();

const showActionBarAlways = isNull(
  localStorage.getItem("settings.showActionBar"),
)
  ? false
  : localStorage.getItem("settings.showActionBar") === "true";

const showActionBar = computed(() => smAndDown.value || showActionBarAlways);

const computedAspectRatio = computed(() => {
  const ratio =
    props.aspectRatio ||
    platformsStore.getAspectRatio(props.platformId || 0) ||
    galleryViewStore.defaultAspectRatioCover;
  return parseFloat(ratio.toString());
});
</script>

<template>
  <v-skeleton-loader
    class="card-skeleton"
    :class="{ 'show-action-bar': showActionBar }"
    :type="type"
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

.card-skeleton.show-action-bar .v-skeleton-loader__button {
  height: 24px;
  margin: 4px;
  flex: 1;
  max-width: unset;
}

.card-skeleton.show-action-bar {
  .v-skeleton-loader__image {
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    border-bottom-left-radius: 0;
    border-bottom-right-radius: 0;
  }

  .v-skeleton-loader__avatar,
  .v-skeleton-loader__chip:nth-of-type(3) {
    bottom: 32px;
  }

  .v-skeleton-loader__actions {
    display: flex;
    flex-wrap: nowrap;
  }
}
</style>
