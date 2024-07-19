<script setup lang="ts">
import GalleryAppBarCollection from "@/components/Gallery/AppBar/Collection/Base.vue";
import FabOverlay from "@/components/Gallery/FabOverlay.vue";
import EmptyCollection from "@/components/common/EmptyCollection.vue";
import EmptyGame from "@/components/common/EmptyGame.vue";
import GameCard from "@/components/common/Game/Card/Base.vue";
import GameDataTable from "@/components/common/Game/Table.vue";
import collectionApi from "@/services/api/collection";
import romApi from "@/services/api/rom";
import storeCollections from "@/stores/collections";
import storeGalleryFilter from "@/stores/galleryFilter";
import storeGalleryView from "@/stores/galleryView";
import storeRoms, { type SimpleRom } from "@/stores/roms";
import type { Events } from "@/types/emitter";
import { normalizeString, views } from "@/utils";
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import { inject, onBeforeUnmount, onMounted, ref } from "vue";
import { onBeforeRouteUpdate, useRoute, useRouter } from "vue-router";
import { useDisplay } from "vuetify";

// Props
const { smAndDown } = useDisplay();
const route = useRoute();
const galleryViewStore = storeGalleryView();
const galleryFilterStore = storeGalleryFilter();
const { scrolledToTop, currentView } = storeToRefs(galleryViewStore);
const collectionsStore = storeCollections();
const romsStore = storeRoms();
const {
  allRoms,
  filteredRoms,
  selectedRoms,
  currentCollection,
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

  await romApi
    .getRoms({
      collectionId: romsStore.currentCollection?.id,
      searchTerm: normalizeString(galleryFilterStore.filterSearch),
    })
    .then(({ data }) => {
      romsStore.set(data);
      romsStore.setFiltered(data, galleryFilterStore);
    })
    .catch((error) => {
      emitter?.emit("snackbarShow", {
        msg: `Couldn't fetch roms for collection ID ${currentCollection.value?.id}: ${error}`,
        icon: "mdi-close-circle",
        color: "red",
        timeout: 4000,
      });
      console.error(
        `Couldn't fetch roms for collection ID ${currentCollection.value?.id}: ${error}`
      );
      noCollectionError.value = true;
    })
    .finally(() => {
      gettingRoms.value = false;
      emitter?.emit("showLoadingDialog", {
        loading: gettingRoms.value,
        scrim: false,
      });
    });
}

function setFilters() {
  galleryFilterStore.setFilterGenre([
    ...new Set(
      romsStore.filteredRoms
        .flatMap((rom) => rom.genres.map((genre) => genre))
        .sort()
    ),
  ]);
  galleryFilterStore.setFilterFranchise([
    ...new Set(
      romsStore.filteredRoms
        .flatMap((rom) => rom.franchises.map((franchise) => franchise))
        .sort()
    ),
  ]);
  galleryFilterStore.setFilterCompany([
    ...new Set(
      romsStore.filteredRoms
        .flatMap((rom) => rom.companies.map((company) => company))
        .sort()
    ),
  ]);
  galleryFilterStore.setFilterCollection([
    ...new Set(
      romsStore.filteredRoms
        .flatMap((rom) => rom.collections.map((collection) => collection))
        .sort()
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
    emitData.event.ctrlKey ||
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
        (a, b) => a - b
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
        romsStore.selectedRoms.includes(emitData.rom) ? index : index - 1
      );
    } else {
      romsStore.updateLastSelected(index);
    }
  } else {
    router.push({ name: "rom", params: { rom: emitData.rom.id } });
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
  scrolledToTop.value = true;
  noCollectionError.value = false;
  itemsShown.value = itemsPerBatch.value;
}

onMounted(async () => {
  const routeCollectionId = Number(route.params.collection);
  const routeCollection = collectionsStore.get(routeCollectionId);

  if (!routeCollection) {
    await collectionApi
      .getCollection(routeCollectionId)
      .then((data) => {
        collectionsStore.add(data.data);
        romsStore.setCurrentCollection(data.data);
      })
      .catch((error) => {
        console.log(error);
        noCollectionError.value = true;
      });
  } else {
    romsStore.setCurrentCollection(routeCollection);
  }
  if (!noCollectionError.value) {
    resetGallery();
    await fetchRoms();
    setFilters();
    window.addEventListener("wheel", onScroll);
    window.addEventListener("scroll", onScroll);
  }
});

onBeforeRouteUpdate(async (to, from) => {
  // Triggers when change param of the same route
  // Reset store if switching to another collection
  if (to.path === from.path) return true;

  resetGallery();

  const routeCollectionId = Number(to.params.collection);
  const routeCollection = collectionsStore.get(routeCollectionId);
  if (!routeCollection) {
    const { data } = await collectionApi.getCollection(routeCollectionId);
    collectionsStore.add(data);
  } else {
    romsStore.setCurrentCollection(routeCollection);
  }

  await fetchRoms();
  setFilters();

  return true;
});

onBeforeUnmount(() => {
  romsStore.setCurrentCollection(null);
  window.removeEventListener("wheel", onScroll);
  window.removeEventListener("scroll", onScroll);
});
</script>

<template>
  <template v-if="!noCollectionError">
    <gallery-app-bar-collection />
    <template v-if="filteredRoms.length > 0">
      <v-row
        no-gutters
        class="overflow-hidden"
        :class="{ 'pa-1': currentView != 2 }"
      >
        <!-- Gallery cards view -->
        <!-- v-show instead of v-if to avoid recalculate on view change -->
        <v-col
          v-for="rom in filteredRoms.slice(0, itemsShown)"
          v-show="currentView != 2"
          :key="rom.id"
          class="pa-1"
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
            show-flags
            show-action-bar
            transform-scale
            with-border
            show-fav
            show-platform-icon
            :with-border-romm-accent="
              romsStore.isSimpleRom(rom) && selectedRoms?.includes(rom)
            "
            @click="onGameClick"
            @touchstart="onGameTouchStart"
            @touchend="onGameTouchEnd"
          />
        </v-col>

        <!-- Gallery list view -->
        <v-col v-show="currentView == 2">
          <game-data-table
            :class="{
              'fill-height-desktop': !smAndDown,
              'fill-height-mobile': smAndDown,
            }"
          />
        </v-col>
      </v-row>
      <fab-overlay />
    </template>
    <template v-else>
      <empty-game v-if="!gettingRoms && galleryFilterStore.isFiltered()" />
    </template>
  </template>

  <empty-collection v-else />
</template>
