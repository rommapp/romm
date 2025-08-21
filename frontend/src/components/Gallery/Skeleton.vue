<script setup lang="ts">
import { views } from "@/utils";
import { storeToRefs } from "pinia";
import storeGalleryView from "@/stores/galleryView";
import storePlatforms from "@/stores/platforms";
import { computed } from "vue";

const props = withDefaults(
  defineProps<{
    platformId?: number;
    aspectRatio?: string | number;
  }>(),
  {
    platformId: undefined,
    aspectRatio: undefined,
  },
);

const galleryViewStore = storeGalleryView();
const platformsStore = storePlatforms();
const { currentView } = storeToRefs(galleryViewStore);

const computedAspectRatio = computed(() => {
  const ratio =
    props.aspectRatio ||
    platformsStore.getAspectRatio(props.platformId || 0) ||
    galleryViewStore.defaultAspectRatioCover;
  return parseFloat(ratio.toString());
});
</script>

<template>
  <v-row no-gutters>
    <v-col>
      <v-row v-if="currentView != 2" no-gutters class="mx-1 mt-3 mr-14">
        <v-col
          v-for="_ in 60"
          class="pa-1 align-self-end"
          :cols="views[currentView]['size-cols']"
          :sm="views[currentView]['size-sm']"
          :md="views[currentView]['size-md']"
          :lg="views[currentView]['size-lg']"
          :xl="views[currentView]['size-xl']"
        >
          <v-skeleton-loader
            type="image, avatar, chip, chip"
            class="card-skeleton"
            :style="{ aspectRatio: computedAspectRatio }"
          />
        </v-col>
      </v-row>

      <v-row class="h-100 mr-13" v-if="currentView == 2" no-gutters>
        <v-col class="h-100 pt-4 pb-2">
          <v-skeleton-loader
            class="mx-2"
            type="table-heading, table-tbody, table-tbody, table-row"
          />
        </v-col>
      </v-row>
    </v-col>
  </v-row>
</template>

<style>
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
</style>
