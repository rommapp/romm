<script setup lang="ts">
import GalleryAppBarCollection from "@/components/Gallery/AppBar/Collection/Base.vue";
import FabOverlay from "@/components/Gallery/FabOverlay.vue";
import EmptyCollection from "@/components/common/EmptyStates/EmptyCollection.vue";
import EmptyGame from "@/components/common/EmptyStates/EmptyGame.vue";
import GameCard from "@/components/common/Game/Card/Base.vue";
import Skeleton from "@/components/Gallery/Skeleton.vue";
import GameDataTable from "@/components/common/Game/Table.vue";
import romApi from "@/services/api/rom";
import storeCollections from "@/stores/collections";
import storeGalleryFilter from "@/stores/galleryFilter";
import storeGalleryView from "@/stores/galleryView";
import storeRoms, { type SimpleRom } from "@/stores/roms";
import type { Events } from "@/types/emitter";
import { views } from "@/utils";
import { ROUTES } from "@/plugins/router";
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
  itemsPerBatch,
  gettingRoms,
} = storeToRefs(romsStore);
const itemsShown = ref(itemsPerBatch.value);
const noCollectionError = ref(false);
const router = useRouter();
let timeout: ReturnType<typeof setTimeout>;
const emitter = inject<Emitter<Events>>("emitter");
emitter?.on("filter", onFilterChange);

// Functions
async function fetchRoms() {
  if (gettingRoms.value) return;

  gettingRoms.value = true;
  emitter?.emit("showLoadingDialog", {
    loading: gettingRoms.value,
    scrim: false,
  });

  try {
    const { data } = await romApi.getRoms({
      collectionId: romsStore.currentCollection?.id,
      virtualCollectionId: romsStore.currentVirtualCollection?.id,
    });
    romsStore.set(data);
    romsStore.setFiltered(data, galleryFilterStore);

    gettingRoms.value = false;
    emitter?.emit("showLoadingDialog", {
      loading: gettingRoms.value,
      scrim: false,
    });
  } catch (error) {
    emitter?.emit("snackbarShow", {
      msg: `Couldn't fetch roms for collection ID ${currentCollection.value?.id}: ${error}`,
      icon: "mdi-close-circle",
      color: "red",
      timeout: 4000,
    });
    console.error(
      `Couldn't fetch roms for collection ID ${currentCollection.value?.id}: ${error}`,
    );
    noCollectionError.value = true;
  } finally {
    gettingRoms.value = false;
    emitter?.emit("showLoadingDialog", {
      loading: gettingRoms.value,
      scrim: false,
    });
  }
}

function setFilters() {
  galleryFilterStore.setFilterGenres([
    ...new Set(
      romsStore.filteredRoms
        .flatMap((rom) => rom.genres.map((genre) => genre))
        .sort(),
    ),
  ]);
  galleryFilterStore.setFilterFranchises([
    ...new Set(
      romsStore.filteredRoms
        .flatMap((rom) => rom.franchises.map((franchise) => franchise))
        .sort(),
    ),
  ]);
  galleryFilterStore.setFilterCompanies([
    ...new Set(
      romsStore.filteredRoms
        .flatMap((rom) => rom.companies.map((company) => company))
        .sort(),
    ),
  ]);
  galleryFilterStore.setFilterCollections([
    ...new Set(
      romsStore.filteredRoms
        .flatMap((rom) => rom.meta_collections.map((collection) => collection))
        .sort(),
    ),
  ]);
  galleryFilterStore.setFilterAgeRatings([
    ...new Set(
      romsStore.filteredRoms
        .flatMap((rom) => rom.age_ratings.map((ageRating) => ageRating))
        .sort(),
    ),
  ]);
}

async function onFilterChange() {
  romsStore.setFiltered(allRoms.value, galleryFilterStore);
  emitter?.emit("updateDataTablePages", null);
}

function onGameClick(emitData: { rom: SimpleRom; event: MouseEvent }) {
  let index = filteredRoms.value.indexOf(emitData.rom);
  if (
    emitData.event.shiftKey ||
    romsStore.selecting ||
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
  if (galleryViewStore.currentView != 2) {
    window.setTimeout(async () => {
      const { scrollTop, scrollHeight, clientHeight } =
        document.documentElement;
      scrolledToTop.value = scrollTop === 0;
      const totalScrollableHeight = scrollHeight - clientHeight;
      const ninetyPercentPoint = totalScrollableHeight * 0.9;
      if (
        scrollTop >= ninetyPercentPoint &&
        itemsShown.value < filteredRoms.value.length
      ) {
        itemsShown.value = itemsShown.value + itemsPerBatch.value;
        setFilters();
        galleryViewStore.scroll = scrollHeight;
      }
    }, 100);
    clearTimeout(timeout);
  }
}

function resetGallery() {
  romsStore.reset();
  galleryFilterStore.reset();
  galleryFilterStore.activeFilterDrawer = false;
  scrolledToTop.value = true;
  noCollectionError.value = false;
  itemsShown.value = itemsPerBatch.value;
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
          setFilters();
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
          setFilters();
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
          setFilters();
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
          setFilters();
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
    <template v-if="gettingRoms">
      <skeleton />
    </template>
    <template v-else>
      <template v-if="filteredRoms.length > 0">
        <v-row v-show="currentView != 2" class="mx-1 mt-3" no-gutters>
          <!-- Gallery cards view -->
          <!-- v-show instead of v-if to avoid recalculate on view change -->
          <v-col
            v-for="rom in filteredRoms.slice(0, itemsShown)"
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
        <v-row class="h-100" v-show="currentView == 2" no-gutters>
          <v-col class="h-100 pt-4 pb-2">
            <game-data-table show-platform-icon class="h-100 mx-2" />
          </v-col>
        </v-row>
        <fab-overlay />
      </template>
      <template v-else>
        <empty-game v-if="!gettingRoms && galleryFilterStore.isFiltered()" />
      </template>
    </template>
  </template>

  <empty-collection v-else />
</template>
