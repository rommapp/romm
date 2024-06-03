<script setup lang="ts">
import GalleryAppBar from "@/components/Gallery/AppBar/Base.vue";
import EmptyGame from "@/components/Gallery/EmptyGame.vue";
import EmptyPlatform from "@/components/Gallery/EmptyPlatform.vue";
import FabBar from "@/components/Gallery/FabBar/Base.vue";
import GameCard from "@/components/Game/Card/Base.vue";
import GameCardFlags from "@/components/Game/Card/Flags.vue";
import GameDataTable from "@/components/Game/Table.vue";
import platformApi from "@/services/api/platform";
import romApi from "@/services/api/rom";
import storeGalleryFilter from "@/stores/galleryFilter";
import storeGalleryView from "@/stores/galleryView";
import storePlatforms from "@/stores/platforms";
import storeRoms, { type SimpleRom } from "@/stores/roms";
import type { Events } from "@/types/emitter";
import { normalizeString, views } from "@/utils";
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import { inject, onBeforeUnmount, onMounted, ref } from "vue";
import {
  onBeforeRouteLeave,
  onBeforeRouteUpdate,
  useRoute,
  useRouter,
} from "vue-router";

// Props
const route = useRoute();
const galleryViewStore = storeGalleryView();
const galleryFilterStore = storeGalleryFilter();
const gettingRoms = ref(false);
const { scrolledToTop } = storeToRefs(galleryViewStore);
const platforms = storePlatforms();
const romsStore = storeRoms();
const {
  allRoms,
  filteredRoms,
  selectedRoms,
  searchRoms,
  platformID,
  itemsPerBatch,
} = storeToRefs(romsStore);
const itemsShown = ref(itemsPerBatch.value);
const noPlatformError = ref(false);
const router = useRouter();
let timeout: ReturnType<typeof setTimeout>;

// Event listeners bus
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
      platformId: platformID.value,
      searchTerm: normalizeString(galleryFilterStore.filterSearch),
    })
    .then(({ data }) => {
      // Add any new roms to the store
      const allRomsSet = [...allRoms.value, ...data];
      romsStore.set(allRomsSet);
      romsStore.setFiltered(allRomsSet, galleryFilterStore);

      if (galleryFilterStore.isFiltered()) {
        const serchedRomsSet = [...searchRoms.value, ...data];
        romsStore.setSearch(serchedRomsSet);
        romsStore.setFiltered(serchedRomsSet, galleryFilterStore);
      }
    })
    .catch((error) => {
      emitter?.emit("snackbarShow", {
        msg: `Couldn't fetch roms for platform ID ${platformID.value}: ${error}`,
        icon: "mdi-close-circle",
        color: "red",
        timeout: 4000,
      });
      console.error(
        `Couldn't fetch roms for platform ID ${platformID.value}: ${error}`
      );
    })
    .finally(() => {
      gettingRoms.value = false;
      emitter?.emit("showLoadingDialog", {
        loading: gettingRoms.value,
        scrim: false,
      });
    });
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
  romsStore.setSearch([]);
  if (!galleryFilterStore.isFiltered()) {
    romsStore.setFiltered(allRoms.value, galleryFilterStore);
    return;
  }
  await fetchRoms();
  emitter?.emit("updateDataTablePages", null);
}

function onScroll() {
  window.setTimeout(async () => {
    const { scrollTop, scrollHeight, clientHeight } = document.documentElement;
    scrolledToTop.value = scrollTop === 0;
    const totalScrollableHeight = scrollHeight - clientHeight;
    const ninetyPercentPoint = totalScrollableHeight * 0.9;
    if (
      scrollTop >= ninetyPercentPoint &&
      itemsShown.value < filteredRoms.value.length
    ) {
      itemsShown.value = itemsShown.value + itemsPerBatch.value;
      setFilters();
    }
  }, 100);
  clearTimeout(timeout);
}

function resetGallery() {
  romsStore.reset();
  scrolledToTop.value = true;
  galleryFilterStore.reset();
  itemsShown.value = itemsPerBatch.value;
}

onMounted(async () => {
  const storedPlatformID = romsStore.platformID;
  const platformID = Number(route.params.platform);

  romsStore.setPlatformID(platformID);

  const platform = platforms.get(platformID);
  if (!platform) {
    // const { data } =
    await platformApi
      .getPlatform(platformID)
      .then((data) => {
        platforms.add(data.data);
      })
      .catch((error) => {
        console.log(error);
        noPlatformError.value = true;
      });
  }

  // If platform is different, reset store and fetch roms
  if (storedPlatformID != platformID) {
    resetGallery();
    await fetchRoms();
  }

  // If platform is the same but there are no roms, fetch them
  if (filteredRoms.value.length == 0) {
    await fetchRoms();
  }
  setFilters();

  window.addEventListener("wheel", onScroll);
  window.addEventListener("scroll", onScroll);
});

onBeforeUnmount(() => {
  window.removeEventListener("wheel", onScroll);
  window.removeEventListener("scroll", onScroll);
});

onBeforeRouteLeave((to, from, next) => {
  if (!to.fullPath.includes(from.path)) {
    resetGallery();
  }
  next();
});

onBeforeRouteUpdate(async (to) => {
  // Triggers when change query param of the same route
  // Reset store if switching to another platform
  resetGallery();

  const platformID = Number(to.params.platform);
  romsStore.setPlatformID(platformID);

  const platform = platforms.get(platformID);
  if (!platform) {
    const { data } = await platformApi.getPlatform(platformID);
    platforms.add(data);
  }

  await fetchRoms();
  setFilters();
});
</script>

<template>
  <gallery-app-bar />

  <template v-if="filteredRoms.length > 0">
    <v-row class="pa-1" no-gutters>
      <!-- Gallery cards view -->
      <!-- v-show instead of v-if to avoid recalculate on view change -->
      <v-col
        v-for="rom in filteredRoms.slice(0, itemsShown)"
        v-show="galleryViewStore.current != 2"
        :key="rom.id"
        class="pa-1"
        :cols="views[galleryViewStore.current]['size-cols']"
        :xs="views[galleryViewStore.current]['size-xs']"
        :sm="views[galleryViewStore.current]['size-sm']"
        :md="views[galleryViewStore.current]['size-md']"
        :lg="views[galleryViewStore.current]['size-lg']"
        :xl="views[galleryViewStore.current]['size-xl']"
      >
        <game-card
          :rom="rom"
          title-on-hover
          show-action-bar
          transform-scale
          @click="onGameClick"
          @touchstart="onGameTouchStart"
          @touchend="onGameTouchEnd"
        >
          <template #prepend-inner>
            <game-card-flags :rom="rom" />
          </template>
        </game-card>
      </v-col>

      <!-- Gallery list view -->
      <v-col v-show="galleryViewStore.current == 2">
        <game-data-table />
      </v-col>
    </v-row>
  </template>

  <template v-else>
    <empty-game v-if="!gettingRoms && galleryFilterStore.isFiltered()" />
  </template>

  <empty-platform v-if="noPlatformError" />

  <fab-bar />
</template>

<style scoped>
#scrollToTop {
  border: 1px solid rgba(var(--v-theme-romm-accent-1));
}
</style>
