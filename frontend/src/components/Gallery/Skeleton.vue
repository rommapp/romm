<script setup lang="ts">
import { storeToRefs } from "pinia";
import Skeleton from "@/components/common/Game/Card/Skeleton.vue";
import { RECENT_ROMS_LIMIT } from "@/services/api/rom";
import storeGalleryView from "@/stores/galleryView";
import storeRoms from "@/stores/roms";
import { views } from "@/utils";

const props = withDefaults(
  defineProps<{
    platformId?: number;
    romCount?: number;
  }>(),
  {
    platformId: undefined,
    romCount: RECENT_ROMS_LIMIT,
  },
);

const galleryViewStore = storeGalleryView();
const romsStore = storeRoms();
const { currentView } = storeToRefs(galleryViewStore);
const { fetchLimit } = storeToRefs(romsStore);
</script>

<template>
  <v-row no-gutters>
    <v-col>
      <v-row v-if="currentView != 2" no-gutters class="mx-1 mt-3 mr-14">
        <v-col
          v-for="index in Math.min(props.romCount, fetchLimit)"
          :key="index"
          class="pa-1 align-self-end"
          :cols="views[currentView]['size-cols']"
          :sm="views[currentView]['size-sm']"
          :md="views[currentView]['size-md']"
          :lg="views[currentView]['size-lg']"
          :xl="views[currentView]['size-xl']"
        >
          <Skeleton :platform-id="props.platformId" />
        </v-col>
      </v-row>

      <v-row v-if="currentView == 2" class="h-100 mr-13" no-gutters>
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
