<script setup lang="ts">
import GalleryAppBarSearch from "@/components/Gallery/AppBar/Search/Base.vue";
import FabOverlay from "@/components/Gallery/FabOverlay.vue";
import EmptySearch from "@/components/common/EmptyStates/EmptySearch.vue";
import EmptyGame from "@/components/common/EmptyStates/EmptyGame.vue";
import GameCard from "@/components/common/Game/Card/Base.vue";
import GameDataTable from "@/components/common/Game/Table.vue";
import storeGalleryFilter from "@/stores/galleryFilter";
import storeGalleryView from "@/stores/galleryView";
import storeRoms, { type SimpleRom } from "@/stores/roms";
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { views } from "@/utils";
import { useI18n } from "vue-i18n";
import { storeToRefs } from "pinia";
import { inject, onBeforeUnmount, onMounted, ref } from "vue";
import { useRouter } from "vue-router";

// Props
const galleryViewStore = storeGalleryView();
const { scrolledToTop, currentView } = storeToRefs(galleryViewStore);
const galleryFilterStore = storeGalleryFilter();
const { searchText } = storeToRefs(galleryFilterStore);
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
let timeout: ReturnType<typeof setTimeout>;
const emitter = inject<Emitter<Events>>("emitter");
emitter?.on("filter", onFilterChange);
const { t } = useI18n();
const router = useRouter();
const initialSearch = ref(false);

// Functions
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
  if (currentView.value != 2) {
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
  itemsShown.value = itemsPerBatch.value;
}

onMounted(async () => {
  currentPlatform.value = null;
  currentCollection.value = null;
  resetGallery();
  window.addEventListener("wheel", onScroll);
  window.addEventListener("scroll", onScroll);
});

onBeforeUnmount(() => {
  window.removeEventListener("wheel", onScroll);
  window.removeEventListener("scroll", onScroll);
  searchText.value = "";
});
</script>

<template>
  <gallery-app-bar-search />
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
          show-platform-icon
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
      <game-data-table class="fill-height" />
    </v-row>
    <fab-overlay />
  </template>
  <template v-else>
    <empty-game
      v-if="!gettingRoms && galleryFilterStore.isFiltered() && initialSearch"
    />
    <empty-search v-else-if="!initialSearch" />
  </template>
</template>
