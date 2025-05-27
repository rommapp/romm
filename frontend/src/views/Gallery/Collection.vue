<script setup lang="ts">
import GalleryAppBarCollection from "@/components/Gallery/AppBar/Collection/Base.vue";
import FabOverlay from "@/components/Gallery/FabOverlay.vue";
import EmptyCollection from "@/components/common/EmptyStates/EmptyCollection.vue";
import EmptyGame from "@/components/common/EmptyStates/EmptyGame.vue";
import GameCard from "@/components/common/Game/Card/Base.vue";
import Skeleton from "@/components/Gallery/Skeleton.vue";
import LoadMoreBtn from "@/components/Gallery/LoadMoreBtn.vue";
import GameTable from "@/components/common/Game/Table.vue";
import storeCollections from "@/stores/collections";
import storeGalleryFilter from "@/stores/galleryFilter";
import storeGalleryView from "@/stores/galleryView";
import storeRoms, { type SimpleRom } from "@/stores/roms";
import type { Events } from "@/types/emitter";
import { views } from "@/utils";
import { ROUTES } from "@/plugins/router";
import { isNull } from "lodash";
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import { inject, onBeforeUnmount, onMounted, ref, watch } from "vue";
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
const router = useRouter();
const emitter = inject<Emitter<Events>>("emitter");
const isHovering = ref(false);
const hoveringRomId = ref();
const openedMenu = ref(false);
const openedMenuRomId = ref();
const storedEnable3DEffect = localStorage.getItem("settings.enable3DEffect");
const enable3DEffect = ref(
  isNull(storedEnable3DEffect) ? false : storedEnable3DEffect === "true",
);
let timeout: ReturnType<typeof setTimeout>;

// Functions
async function fetchRoms() {
  if (fetchingRoms.value) return;
  emitter?.emit("showLoadingDialog", {
    loading: true,
    scrim: false,
  });

  romsStore
    .fetchRoms(galleryFilterStore)
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

function onHover(emitData: { isHovering: boolean; id: number }) {
  isHovering.value = emitData.isHovering;
  hoveringRomId.value = emitData.id;
}

function onOpenedMenu(emitData: { openedMenu: boolean; id: number }) {
  openedMenu.value = emitData.openedMenu;
  openedMenuRomId.value = emitData.id;
}

function onClosedMenu() {
  openedMenu.value = false;
  openedMenuRomId.value = null;
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
    scrolledToTop.value = window.scrollY === 0;
    if (
      window.innerHeight + window.scrollY >= document.body.offsetHeight - 60 &&
      fetchTotalRoms.value > allRoms.value.length
    ) {
      await fetchRoms();
    }
  }, 100);
}

function resetGallery() {
  romsStore.reset();
  galleryFilterStore.resetFilters();
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
          resetGallery();
          romsStore.setCurrentCollection(collection);
          document.title = `${collection.name}`;
          await fetchRoms();
        }

        window.addEventListener("scroll", onScroll);
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
          resetGallery();
          romsStore.setCurrentVirtualCollection(collection);
          document.title = `${collection.name}`;
          await fetchRoms();
        }

        window.addEventListener("scroll", onScroll);
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
          document.title = `${collection.name}`;
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
          document.title = `${collection.name}`;
          await fetchRoms();
        }
      }
    },
    { immediate: true }, // Ensure watcher is triggered immediately
  );
});

onBeforeUnmount(() => {
  window.removeEventListener("scroll", onScroll);
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
        <v-row v-if="currentView != 2" class="mx-1 my-3 mr-14" no-gutters>
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
            :style="{
              zIndex:
                (isHovering && hoveringRomId === rom.id) ||
                (openedMenu && openedMenuRomId === rom.id)
                  ? 1100
                  : 1,
            }"
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
              :sizeActionBar="currentView"
              :enable3DTilt="enable3DEffect"
              @click="onGameClick"
              @touchstart="onGameTouchStart"
              @touchend="onGameTouchEnd"
              @hover="onHover"
              @openedmenu="onOpenedMenu"
              @closedmenu="onClosedMenu"
            />
          </v-col>
        </v-row>

        <!-- Gallery list view -->
        <v-row class="mr-13" v-if="currentView == 2" no-gutters>
          <v-col class="my-4">
            <game-table show-platform-icon class="mx-2" />
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
