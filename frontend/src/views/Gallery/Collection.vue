<script setup lang="ts">
import GalleryAppBarCollection from "@/components/Gallery/AppBar/Collection/Base.vue";
import FabOverlay from "@/components/Gallery/FabOverlay.vue";
import EmptyCollection from "@/components/common/EmptyStates/EmptyCollection.vue";
import EmptyGame from "@/components/common/EmptyStates/EmptyGame.vue";
import GameCard from "@/components/common/Game/Card/Base.vue";
import Skeleton from "@/components/Gallery/Skeleton.vue";
import LoadMoreBtn from "@/components/Gallery/LoadMoreBtn.vue";
import GameDataTable from "@/components/common/Game/Table.vue";
import storeCollections from "@/stores/collections";
import storeGalleryFilter from "@/stores/galleryFilter";
import storeGalleryView from "@/stores/galleryView";
import storeRoms, { type SimpleRom } from "@/stores/roms";
import type { Events } from "@/types/emitter";
import { views } from "@/utils";
import { ROUTES } from "@/plugins/router";
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import {
  inject,
  onBeforeUnmount,
  onMounted,
  ref,
  watch,
  type VNodeRef,
} from "vue";
import { onBeforeRouteUpdate, useRoute, useRouter } from "vue-router";

// Props
const route = useRoute();
const galleryViewStore = storeGalleryView();
const galleryFilterStore = storeGalleryFilter();
const { scrolledToTop, currentView } = storeToRefs(galleryViewStore);
const collectionsStore = storeCollections();
const { allCollections, virtualCollections } = storeToRefs(collectionsStore);
const romsStore = storeRoms();
const {
  allRoms,
  filteredRoms,
  selectedRoms,
  currentPlatform,
  currentCollection,
  currentVirtualCollection,
  fetchingRoms,
  fetchTotalRoms,
} = storeToRefs(romsStore);
const noCollectionError = ref(false);
const galleryRef = ref<VNodeRef | undefined>(undefined);
const router = useRouter();
let timeout: ReturnType<typeof setTimeout>;
const emitter = inject<Emitter<Events>>("emitter");

// Functions
async function fetchRoms() {
  if (fetchingRoms.value) return;
  emitter?.emit("showLoadingDialog", {
    loading: true,
    scrim: false,
  });

  romsStore
    .fetchRoms(
      {
        collectionId: romsStore.currentCollection?.id,
        virtualCollectionId: romsStore.currentVirtualCollection?.id,
      },
      galleryFilterStore,
    )
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
      noCollectionError.value = true;
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
  } else if (emitData.event.metaKey || emitData.event.ctrlKey) {
    const link = router.resolve({
      name: ROUTES.ROM,
      params: { rom: emitData.rom.id },
    });
    window.open(link.href, "_blank");
  } else {
    router.push({ name: ROUTES.ROM, params: { rom: emitData.rom.id } });
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

function onScroll() {
  clearTimeout(timeout);

  window.setTimeout(async () => {
    if (!galleryRef.value) return;

    const rect = galleryRef.value.$el.getBoundingClientRect();
    scrolledToTop.value = rect.top === 0;
    if (
      rect.bottom - window.innerHeight < 60 &&
      fetchTotalRoms.value > allRoms.value.length
    ) {
      await fetchRoms();
    }
  }, 100);
}

function resetGallery() {
  romsStore.reset();
  galleryFilterStore.reset();
  galleryFilterStore.activeFilterDrawer = false;
  scrolledToTop.value = true;
  noCollectionError.value = false;
}

onMounted(async () => {
  const routeCollectionId = route.params.collection;
  currentPlatform.value = null;

  watch(
    () => allCollections.value,
    async (collections) => {
      if (
        collections.length > 0 &&
        collections.some(
          (collection) => collection.id === Number(routeCollectionId),
        )
      ) {
        const collection = collections.find(
          (collection) => collection.id === Number(routeCollectionId),
        );

        // Check if the current platform is different or no ROMs have been loaded
        if (
          (currentVirtualCollection.value?.id !== routeCollectionId ||
            allRoms.value.length === 0) &&
          collection
        ) {
          romsStore.setCurrentCollection(collection);
          romsStore.setCurrentVirtualCollection(null);
          resetGallery();
          await fetchRoms();
        }

        window.addEventListener("wheel", onScroll);
        window.addEventListener("scroll", onScroll);
        window.addEventListener("touchmove", onScroll);
      }
    },
    { immediate: true }, // Ensure watcher is triggered immediately
  );

  watch(
    () => virtualCollections.value,
    async (collections) => {
      if (
        collections.length > 0 &&
        collections.some((collection) => collection.id === routeCollectionId)
      ) {
        const collection = collections.find(
          (collection) => collection.id === routeCollectionId,
        );

        // Check if the current platform is different or no ROMs have been loaded
        if (
          (currentVirtualCollection.value?.id !== routeCollectionId ||
            allRoms.value.length === 0) &&
          collection
        ) {
          romsStore.setCurrentCollection(null);
          romsStore.setCurrentVirtualCollection(collection);
          resetGallery();
          await fetchRoms();
        }

        window.addEventListener("wheel", onScroll);
        window.addEventListener("scroll", onScroll);
        window.addEventListener("touchmove", onScroll);
      }
    },
    { immediate: true }, // Ensure watcher is triggered immediately
  );
});

onBeforeRouteUpdate(async (to, from) => {
  // Triggers when change param of the same route
  // Reset store if switching to another collection
  if (to.path === from.path) return true;

  resetGallery();

  const routeCollectionId = to.params.collection;

  watch(
    () => allCollections.value,
    async (collections) => {
      if (collections.length > 0) {
        const collection = collections.find(
          (collection) => collection.id === Number(routeCollectionId),
        );

        // Only trigger fetchRoms if switching platforms or ROMs are not loaded
        if (
          (currentCollection.value?.id !== Number(routeCollectionId) ||
            allRoms.value.length === 0) &&
          collection
        ) {
          romsStore.setCurrentCollection(collection);
          romsStore.setCurrentVirtualCollection(null);
          await fetchRoms();
        }
      }
    },
    { immediate: true }, // Ensure watcher is triggered immediately
  );

  watch(
    () => virtualCollections.value,
    async (collections) => {
      if (collections.length > 0) {
        const collection = collections.find(
          (collection) => collection.id === routeCollectionId,
        );

        // Only trigger fetchRoms if switching platforms or ROMs are not loaded
        if (
          (currentVirtualCollection.value?.id !== routeCollectionId ||
            allRoms.value.length === 0) &&
          collection
        ) {
          romsStore.setCurrentCollection(null);
          romsStore.setCurrentVirtualCollection(collection);
          await fetchRoms();
        }
      }
    },
    { immediate: true }, // Ensure watcher is triggered immediately
  );
});

onBeforeUnmount(() => {
  window.removeEventListener("wheel", onScroll);
  window.removeEventListener("scroll", onScroll);
  window.removeEventListener("touchmove", onScroll);
});
</script>

<template>
  <template v-if="!noCollectionError">
    <gallery-app-bar-collection />
    <template v-if="fetchingRoms && filteredRoms.length === 0">
      <skeleton />
    </template>
    <template v-else>
      <template v-if="filteredRoms.length > 0">
        <v-row
          ref="galleryRef"
          v-if="currentView != 2"
          class="mx-1 mt-3"
          no-gutters
        >
          <!-- Gallery cards view -->
          <!-- v-show instead of v-if to avoid recalculate on view change -->
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
            <game-card
              :key="rom.updated_at"
              :rom="rom"
              title-on-hover
              pointer-on-hover
              with-link
              show-flags
              show-fav
              transform-scale
              show-action-bar
              show-platform-icon
              :with-border-primary="
                romsStore.isSimpleRom(rom) && selectedRoms?.includes(rom)
              "
              @click="onGameClick"
              @touchstart="onGameTouchStart"
              @touchend="onGameTouchEnd"
            />
          </v-col>
        </v-row>

        <!-- Gallery list view -->
        <v-row
          ref="galleryRef"
          class="h-100"
          v-if="currentView == 2"
          no-gutters
        >
          <v-col class="h-100 pt-4 pb-2">
            <game-data-table show-platform-icon class="h-100 mx-2" />
          </v-col>
        </v-row>

        <load-more-btn :fetchRoms="fetchRoms" />
        <fab-overlay />
      </template>
      <template v-else>
        <empty-game v-if="!fetchingRoms" />
      </template>
    </template>
  </template>

  <empty-collection v-else />
</template>
