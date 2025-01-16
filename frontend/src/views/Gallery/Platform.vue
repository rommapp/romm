<script setup lang="ts">
import GalleryAppBar from "@/components/Gallery/AppBar/Platform/Base.vue";
import FabOverlay from "@/components/Gallery/FabOverlay.vue";
import EmptyGame from "@/components/common/EmptyStates/EmptyGame.vue";
import EmptyPlatform from "@/components/common/EmptyStates/EmptyPlatform.vue";
import GameCard from "@/components/common/Game/Card/Base.vue";
import GameDataTable from "@/components/common/Game/Table.vue";
import romApi from "@/services/api/rom";
import storeGalleryFilter, { type FilterType } from "@/stores/galleryFilter";
import storeGalleryView from "@/stores/galleryView";
import storePlatforms from "@/stores/platforms";
import storeRoms, { type SimpleRom } from "@/stores/roms";
import type { Events } from "@/types/emitter";
import { normalizeString, views } from "@/utils";
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import { inject, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { onBeforeRouteUpdate, useRoute, useRouter } from "vue-router";
import { useDisplay } from "vuetify";

// Props
const { smAndDown } = useDisplay();
const route = useRoute();
const galleryViewStore = storeGalleryView();
const galleryFilterStore = storeGalleryFilter();
const { scrolledToTop, currentView } = storeToRefs(galleryViewStore);
const platformsStore = storePlatforms();
const { allPlatforms } = storeToRefs(platformsStore);
const romsStore = storeRoms();
const {
  allRoms,
  filteredRoms,
  selectedRoms,
  currentPlatform,
  currentCollection,
  itemsPerBatch,
  gettingRoms,
} = storeToRefs(romsStore);
const itemsShown = ref(itemsPerBatch.value);
const noPlatformError = ref(false);
const router = useRouter();
let timeout: ReturnType<typeof setTimeout>;
const emitter = inject<Emitter<Events>>("emitter");
emitter?.on("filter", onFilterChange);

// Functions
function fetchRoms() {
  if (gettingRoms.value) return;

  gettingRoms.value = true;
  emitter?.emit("showLoadingDialog", {
    loading: gettingRoms.value,
    scrim: false,
  });

  romApi
    .getRoms({
      platformId: romsStore.currentPlatform?.id,
      searchTerm: normalizeString(galleryFilterStore.filterText),
    })
    .then(({ data }) => {
      romsStore.set(data);
      romsStore.setFiltered(data, galleryFilterStore);
    })
    .catch((error) => {
      emitter?.emit("snackbarShow", {
        msg: `Couldn't fetch roms for platform ID ${currentPlatform.value?.id}: ${error}`,
        icon: "mdi-close-circle",
        color: "red",
        timeout: 4000,
      });
      console.error(
        `Couldn't fetch roms for platform ID ${currentPlatform.value?.id}: ${error}`,
      );
      noPlatformError.value = true;
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
        .flatMap((rom) => rom.collections.map((collection) => collection))
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
      name: "rom",
      params: { rom: emitData.rom.id },
    });
    window.open(link.href, "_blank");
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
  galleryFilterStore.activeFilterDrawer = false;
  scrolledToTop.value = true;
  noPlatformError.value = false;
  itemsShown.value = itemsPerBatch.value;
}

const filterToSetFilter: Record<FilterType, Function> = {
  genres: galleryFilterStore.setSelectedFilterGenre,
  franchises: galleryFilterStore.setSelectedFilterFranchise,
  collections: galleryFilterStore.setSelectedFilterCollection,
  companies: galleryFilterStore.setSelectedFilterCompany,
  age_ratings: galleryFilterStore.setSelectedFilterAgeRating,
  status: galleryFilterStore.setSelectedFilterStatus,
};

onMounted(async () => {
  const routePlatformId = Number(route.params.platform);
  currentCollection.value = null;

  watch(
    () => allPlatforms.value,
    (platforms) => {
      if (platforms.length > 0) {
        if (platforms.some((platform) => platform.id === routePlatformId)) {
          const platform = platforms.find(
            (platform) => platform.id === routePlatformId,
          );

          // Check if the current platform is different or no ROMs have been loaded
          if (
            (currentPlatform.value?.id !== routePlatformId ||
              allRoms.value.length === 0) &&
            platform
          ) {
            romsStore.setCurrentPlatform(platform);
            resetGallery();
            fetchRoms();
            setFilters();
          }

          // Check for query params to set filters
          if (route.query.filter && route.query.value) {
            const filter = route.query.filter as FilterType;
            const value = route.query.value as string;
            filterToSetFilter[filter](value);
            onFilterChange(); // Update the UI
            router.replace({ query: {} }); // Clear query params
          }

          window.addEventListener("wheel", onScroll);
          window.addEventListener("scroll", onScroll);
        } else {
          noPlatformError.value = true;
        }
      }
    },
    { immediate: true }, // Ensure watcher is triggered immediately
  );
});

onBeforeRouteUpdate(async (to, from) => {
  // Avoid unnecessary actions if navigating within the same path
  if (to.path === from.path) return;

  resetGallery();

  const routePlatformId = Number(to.params.platform);

  watch(
    () => allPlatforms.value,
    (platforms) => {
      if (platforms.length > 0) {
        const platform = platforms.find(
          (platform) => platform.id === routePlatformId,
        );

        // Only trigger fetchRoms if switching platforms or ROMs are not loaded
        if (
          (currentPlatform.value?.id !== routePlatformId ||
            allRoms.value.length === 0) &&
          platform
        ) {
          romsStore.setCurrentPlatform(platform);
          fetchRoms();
          setFilters();
        } else {
          noPlatformError.value = true;
        }
      }
    },
    { immediate: true }, // Ensure watcher is triggered immediately
  );
});

onBeforeUnmount(() => {
  window.removeEventListener("wheel", onScroll);
  window.removeEventListener("scroll", onScroll);
});
</script>

<template>
  <template v-if="!noPlatformError">
    <gallery-app-bar />
    <v-row v-if="gettingRoms" no-gutters class="pa-1"
      ><v-col
        v-for="_ in 60"
        class="pa-1 align-self-end"
        :cols="views[currentView]['size-cols']"
        :sm="views[currentView]['size-sm']"
        :md="views[currentView]['size-md']"
        :lg="views[currentView]['size-lg']"
        :xl="views[currentView]['size-xl']"
        ><v-skeleton-loader type="card" /></v-col
    ></v-row>
    <template v-if="filteredRoms.length > 0">
      <v-row v-show="currentView != 2" class="pa-1" no-gutters>
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
            v-if="currentPlatform"
            :key="rom.updated_at"
            :rom="rom"
            title-on-hover
            pointer-on-hover
            with-link
            show-flags
            show-action-bar
            show-fav
            transform-scale
            with-border
            :with-border-romm-accent="
              romsStore.isSimpleRom(rom) && selectedRoms?.includes(rom)
            "
            @click="onGameClick"
            @touchstart="onGameTouchStart"
            @touchend="onGameTouchEnd"
          />
        </v-col>
      </v-row>

      <!-- Gallery list view -->
      <v-row v-show="currentView == 2" class="h-100" no-gutters>
        <game-data-table class="h-100" />
      </v-row>
      <fab-overlay />
    </template>
    <template v-else>
      <empty-game v-if="!gettingRoms && galleryFilterStore.isFiltered()" />
    </template>
  </template>

  <empty-platform v-else />
</template>
