<script setup lang="ts">
import { useLocalStorage, useScroll } from "@vueuse/core";
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import { inject, onMounted, ref, watch } from "vue";
import { onBeforeRouteUpdate, useRoute } from "vue-router";
import GalleryAppBar from "@/components/Gallery/AppBar/Platform/Base.vue";
import FabOverlay from "@/components/Gallery/FabOverlay.vue";
import LoadMoreBtn from "@/components/Gallery/LoadMoreBtn.vue";
import Skeleton from "@/components/Gallery/Skeleton.vue";
import EmptyGame from "@/components/common/EmptyStates/EmptyGame.vue";
import EmptyPlatform from "@/components/common/EmptyStates/EmptyPlatform.vue";
import GameCard from "@/components/common/Game/Card/Base.vue";
import GameTable from "@/components/common/Game/VirtualTable.vue";
import storeGalleryFilter from "@/stores/galleryFilter";
import storeGalleryView from "@/stores/galleryView";
import storePlatforms from "@/stores/platforms";
import storeRoms, { type SimpleRom } from "@/stores/roms";
import type { Events } from "@/types/emitter";
import { views } from "@/utils";

const route = useRoute();
const galleryViewStore = storeGalleryView();
const galleryFilterStore = storeGalleryFilter();
const { scrolledToTop, currentView } = storeToRefs(galleryViewStore);
const platformsStore = storePlatforms();
const { filteredPlatforms } = storeToRefs(platformsStore);
const romsStore = storeRoms();
const {
  filteredRoms,
  selectedRoms,
  currentPlatform,
  currentCollection,
  fetchingRoms,
  fetchTotalRoms,
} = storeToRefs(romsStore);
const noPlatformError = ref(false);
const emitter = inject<Emitter<Events>>("emitter");
const enable3DEffect = useLocalStorage("settings.enable3DEffect", false);
let timeout: ReturnType<typeof setTimeout>;

async function fetchRoms() {
  if (fetchingRoms.value) return;

  emitter?.emit("showLoadingDialog", {
    loading: true,
    scrim: false,
  });

  romsStore
    .fetchRoms({ galleryFilter: galleryFilterStore })
    .then(() => {
      emitter?.emit("showLoadingDialog", {
        loading: false,
        scrim: false,
      });
    })
    .catch((error) => {
      emitter?.emit("snackbarShow", {
        msg: `Couldn't fetch roms for platform ID ${currentPlatform.value?.id}: ${error}`,
        icon: "mdi-close-circle",
        color: "red",
        timeout: 4000,
      });
      noPlatformError.value = true;
      emitter?.emit("showLoadingDialog", {
        loading: false,
        scrim: false,
      });
    });
}

function onGameClick(emitData: { rom: SimpleRom; event: MouseEvent }) {
  let index = filteredRoms.value.indexOf(emitData.rom);
  if (
    emitData.event.shiftKey ||
    romsStore.selectingRoms ||
    romsStore.selectedRoms.length > 0
  ) {
    emitData.event.preventDefault();
    emitData.event.stopPropagation();
    if (!selectedRoms.value.includes(emitData.rom)) {
      romsStore.addToSelection(emitData.rom);
    } else {
      romsStore.removeFromSelection(emitData.rom);
    }
    if (emitData.event.shiftKey) {
      const [start, end] = [romsStore.lastSelectedIndex, index].sort(
        (a, b) => a - b,
      );
      if (romsStore.selectedRoms.includes(emitData.rom)) {
        for (let i = start + 1; i < end; i++) {
          romsStore.addToSelection(filteredRoms.value[i]);
        }
      } else {
        for (let i = start; i <= end; i++) {
          romsStore.removeFromSelection(filteredRoms.value[i]);
        }
      }
      romsStore.updateLastSelected(
        romsStore.selectedRoms.includes(emitData.rom) ? index : index - 1,
      );
    } else {
      romsStore.updateLastSelected(index);
    }
  }
}

function onGameTouchStart(emitData: { rom: SimpleRom; event: TouchEvent }) {
  timeout = setTimeout(() => {
    romsStore.addToSelection(emitData.rom);
  }, 500);
}

function onGameTouchEnd() {
  clearTimeout(timeout);
}

const { y: documentY } = useScroll(document.body, { throttle: 500 });

watch(documentY, () => {
  clearTimeout(timeout);

  window.setTimeout(async () => {
    scrolledToTop.value = documentY.value === 0;
    if (
      documentY.value + window.innerHeight >=
        document.body.scrollHeight - 300 &&
      fetchTotalRoms.value > filteredRoms.value.length
    ) {
      await fetchRoms();
    }
  }, 100);
});

function resetGallery() {
  romsStore.reset();
  galleryFilterStore.resetFilters();
  galleryFilterStore.activeFilterDrawer = false;
  scrolledToTop.value = true;
  noPlatformError.value = false;
}

onMounted(async () => {
  const routePlatformId = Number(route.params.platform);
  currentCollection.value = null;

  watch(
    () => filteredPlatforms.value,
    async (platforms) => {
      if (platforms.length > 0) {
        const platform = platforms.find(
          (platform) => platform.id === routePlatformId,
        );

        if (!platform) {
          noPlatformError.value = true;
          return;
        }

        // Check if the current platform is different or no ROMs have been loaded
        if (
          currentPlatform.value?.id !== routePlatformId ||
          filteredRoms.value.length === 0
        ) {
          if (currentPlatform.value) resetGallery();
          romsStore.setCurrentPlatform(platform);
          document.title = platform.display_name;
          await fetchRoms();
        }
      }
    },
    { immediate: true },
  );
});

onBeforeRouteUpdate(async (to, from) => {
  // Avoid unnecessary actions if navigating within the same path
  if (to.path === from.path) return;

  const routePlatformId = Number(to.params.platform);

  watch(
    () => filteredPlatforms.value,
    async (platforms) => {
      if (platforms.length > 0) {
        const platform = platforms.find(
          (platform) => platform.id === routePlatformId,
        );

        if (!platform) {
          noPlatformError.value = true;
          return;
        }

        // Check if the current platform is different or no ROMs have been loaded
        if (
          currentPlatform.value?.id !== routePlatformId ||
          filteredRoms.value.length === 0
        ) {
          if (currentPlatform.value) resetGallery();
          romsStore.setCurrentPlatform(platform);
          document.title = platform.display_name;
          await fetchRoms();
        }
      }
    },
    { immediate: true }, // Ensure watcher is triggered immediately
  );
});
</script>

<template>
  <template v-if="!noPlatformError">
    <GalleryAppBar />
    <template
      v-if="currentPlatform && fetchingRoms && filteredRoms.length === 0"
    >
      <Skeleton
        :platform-id="currentPlatform.id"
        :rom-count="currentPlatform.rom_count"
      />
    </template>
    <template v-else>
      <template v-if="filteredRoms.length > 0">
        <v-row v-if="currentView != 2" class="mx-1 my-3 mr-14" no-gutters>
          <!-- Gallery cards view -->
          <v-col
            v-for="rom in filteredRoms"
            :key="rom.id"
            class="pa-1 align-self-end"
            :cols="views[currentView]['size-cols']"
            :sm="views[currentView]['size-sm']"
            :md="views[currentView]['size-md']"
            :lg="views[currentView]['size-lg']"
            :xl="views[currentView]['size-xl']"
          >
            <GameCard
              :key="rom.id"
              :rom="rom"
              title-on-hover
              pointer-on-hover
              with-link
              transform-scale
              show-action-bar
              show-chips
              :show-platform-icon="false"
              :with-border-primary="
                romsStore.isSimpleRom(rom) && selectedRoms?.includes(rom)
              "
              :size-action-bar="currentView"
              :enable3-d-tilt="enable3DEffect"
              @click="onGameClick"
              @touchstart="onGameTouchStart"
              @touchend="onGameTouchEnd"
            />
          </v-col>
        </v-row>

        <!-- Gallery list view -->
        <v-row v-if="currentView == 2" class="mr-13" no-gutters>
          <v-col class="my-4">
            <GameTable class="mx-2" />
          </v-col>
        </v-row>

        <LoadMoreBtn :fetch-roms="fetchRoms" />
      </template>
      <template v-else>
        <EmptyGame v-if="filteredPlatforms.length > 0 && !fetchingRoms" />
      </template>
    </template>
    <FabOverlay />
  </template>

  <EmptyPlatform v-else />
</template>
