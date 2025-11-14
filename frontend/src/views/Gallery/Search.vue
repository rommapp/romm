<script setup lang="ts">
import { useLocalStorage, useScroll } from "@vueuse/core";
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import { inject, onMounted, onUnmounted, ref, watch } from "vue";
import GalleryAppBarSearch from "@/components/Gallery/AppBar/Search/Base.vue";
import FabOverlay from "@/components/Gallery/FabOverlay.vue";
import LoadMoreBtn from "@/components/Gallery/LoadMoreBtn.vue";
import Skeleton from "@/components/Gallery/Skeleton.vue";
import EmptyGame from "@/components/common/EmptyStates/EmptyGame.vue";
import EmptySearch from "@/components/common/EmptyStates/EmptySearch.vue";
import GameCard from "@/components/common/Game/Card/Base.vue";
import GameTable from "@/components/common/Game/VirtualTable.vue";
import storeGalleryFilter from "@/stores/galleryFilter";
import storeGalleryView from "@/stores/galleryView";
import storeRoms, { type SimpleRom } from "@/stores/roms";
import type { Events } from "@/types/emitter";
import { views } from "@/utils";

const galleryViewStore = storeGalleryView();
const { scrolledToTop, currentView } = storeToRefs(galleryViewStore);
const galleryFilterStore = storeGalleryFilter();
const { searchTerm } = storeToRefs(galleryFilterStore);
const romsStore = storeRoms();
const {
  filteredRoms,
  selectedRoms,
  fetchingRoms,
  initialSearch,
  fetchTotalRoms,
} = storeToRefs(romsStore);
const emitter = inject<Emitter<Events>>("emitter");
const isHovering = ref(false);
const hoveringRomId = ref<number>();
const openedMenu = ref(false);
const openedMenuRomId = ref<number>();
const enable3DEffect = useLocalStorage("settings.enable3DEffect", false);
let timeout: ReturnType<typeof setTimeout>;

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
  openedMenuRomId.value = undefined;
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

function fetchRoms() {
  romsStore
    .fetchRoms({ galleryFilter: galleryFilterStore })
    .catch((error) => {
      emitter?.emit("snackbarShow", {
        msg: `Couldn't fetch roms: ${error}`,
        icon: "mdi-close-circle",
        color: "red",
        timeout: 4000,
      });
    })
    .finally(() => {
      galleryFilterStore.activeFilterDrawer = false;
    });
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

onMounted(async () => {
  scrolledToTop.value = true;
});

onUnmounted(() => {
  searchTerm.value = "";
});
</script>

<template>
  <GalleryAppBarSearch />
  <template v-if="fetchingRoms && filteredRoms.length === 0">
    <Skeleton />
  </template>
  <template v-else>
    <template v-if="filteredRoms.length > 0">
      <v-row v-if="currentView != 2" class="mx-1 my-3 mr-14" no-gutters>
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
                ? 1000
                : 1,
          }"
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
            :with-border-primary="
              romsStore.isSimpleRom(rom) && selectedRoms?.includes(rom)
            "
            :enable3-d-tilt="enable3DEffect"
            :size-action-bar="currentView"
            @click="onGameClick"
            @touchstart="onGameTouchStart"
            @touchend="onGameTouchEnd"
            @hover="onHover"
            @focus="onHover"
            @openedmenu="onOpenedMenu"
            @closedmenu="onClosedMenu"
          />
        </v-col>
      </v-row>

      <!-- Gallery list view -->
      <v-row v-else class="mr-13" no-gutters>
        <v-col class="my-4">
          <GameTable show-platform-icon class="mx-2" />
        </v-col>
      </v-row>

      <LoadMoreBtn :fetch-roms="fetchRoms" />
      <FabOverlay />
    </template>
    <template v-else>
      <EmptyGame v-if="!fetchingRoms && initialSearch" />
      <EmptySearch v-else-if="!initialSearch" />
    </template>
  </template>
</template>
