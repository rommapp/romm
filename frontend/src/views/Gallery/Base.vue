<script setup>
import { ref, inject, onMounted, onBeforeUnmount } from "vue";
import { onBeforeRouteUpdate, useRoute } from "vue-router";
import { fetchRomsApi } from "@/services/api";
import socket from "@/services/socket";
import { views, normalizeString } from "@/utils/utils";
import storeGalleryFilter from "@/stores/galleryFilter";
import storeGalleryView from "@/stores/galleryView";
import storeRoms from "@/stores/roms";
import storeScanning from "@/stores/scanning";
import FilterBar from "@/components/GalleryAppBar/FilterBar.vue";
import GalleryViewBtn from "@/components/GalleryAppBar/GalleryViewBtn.vue";
import GameCard from "@/components/Game/Card/Base.vue";
import GameDataTable from "@/components/Game/DataTable/Base.vue";
import SearchRomDialog from "@/components/Dialog/Rom/SearchRom.vue";
import EditRomDialog from "@/components/Dialog/Rom/EditRom.vue";
import DeleteRomDialog from "@/components/Dialog/Rom/DeleteRom.vue";
import LoadingDialog from "@/components/Dialog/Loading.vue";
import FabMenu from "@/components/FabMenu/Base.vue";

// Props
const route = useRoute();
const roms = ref([]);
const searchRoms = ref([]);
const filteredRoms = ref([]);
const galleryView = storeGalleryView();
const galleryFilter = storeGalleryFilter();
const gettingRoms = ref(false);
const scanning = storeScanning();
const cursor = ref("");
const searchCursor = ref("");
const romsStore = storeRoms();
const fabMenu = ref(false);
const scrolledToTop = ref(true);

// Event listeners bus
const emitter = inject("emitter");
emitter.on("filter", onFilterChange);
emitter.on("openFabMenu", (open) => {
  fabMenu.value = open;
});

socket.on("scan:done", () => {
  scanning.set(false);
  emitter.emit("snackbarShow", {
    msg: "Scan completed successfully!",
    icon: "mdi-check-bold",
    color: "green",
  });
  socket.disconnect();
  emitter.emit("refreshDrawer");
  emitter.emit("refreshView");
});

socket.on("scan:done_ko", (msg) => {
  scanning.set(false);
  emitter.emit("snackbarShow", {
    msg: `Scan couldn't be completed. Something went wrong: ${msg}`,
    icon: "mdi-close-circle",
    color: "red",
  });
  socket.disconnect();
});

// Functions
async function scan() {
  scanning.set(true);
  emitter.emit("snackbarShow", {
    msg: `Scanning ${route.params.platform}...`,
    icon: "mdi-loading mdi-spin",
    color: "romm-accent-1",
  });

  if (!socket.connected) socket.connect();
  socket.emit("scan", {
    platforms: [route.params.platform],
    rescan: false,
  });
}

async function fetchRoms(platform) {
  const isFiltered = normalizeString(galleryFilter.value).trim() != "";

  if (
    (searchCursor.value === null && isFiltered) ||
    (cursor.value === null && !isFiltered) ||
    gettingRoms.value
  )
    return;

  gettingRoms.value = true;
  emitter.emit("showLoadingDialog", {
    loading: gettingRoms.value,
    scrim: false,
  });

  await fetchRomsApi({
    platform: platform,
    cursor: isFiltered ? searchCursor.value : cursor.value,
    searchTerm: normalizeString(galleryFilter.value),
  })
    .then((response) => {
      if (isFiltered) {
        searchCursor.value = response.data.next_page;
        searchRoms.value = [...searchRoms.value, ...response.data.items];
        filteredRoms.value = searchRoms.value;
      } else {
        cursor.value = response.data.next_page;
        roms.value = [...roms.value, ...response.data.items];
        filteredRoms.value = roms.value;
      }
    })
    .catch((error) => {
      console.error(`Couldn't fetch roms for ${platform}: ${error}`);
    })
    .finally(() => {
      gettingRoms.value = false;
      emitter.emit("showLoadingDialog", {
        loading: gettingRoms.value,
        scrim: false,
      });
    });
}

function onFilterChange() {
  searchCursor.value = "";
  searchRoms.value = [];

  if (galleryFilter.value === "") {
    filteredRoms.value = roms.value;
    return;
  }

  fetchRoms(route.params.platform);
}

function onScroll() {
  const { scrollTop, scrollHeight, clientHeight } = document.documentElement;
  scrolledToTop.value = scrollTop === 0;

  if (!cursor.value && !searchCursor.value) return;

  const scrollOffset = 60;
  if (scrollTop + clientHeight + scrollOffset >= scrollHeight) {
    fetchRoms(route.params.platform);
  }
}

function toTop() {
  window.scrollTo({
    top: 0,
    left: 0,
    behavior: "smooth",
  });
}

function selectRom({ event, index, selected }) {
  if (event.shiftKey) {
    const [start, end] = [romsStore.lastSelectedIndex, index].sort(
      (a, b) => a - b
    );
    if (selected) {
      for (let i = start + 1; i < end; i++) {
        romsStore.addSelectedRoms(filteredRoms.value[i]);
      }
    } else {
      for (let i = start; i <= end; i++) {
        romsStore.removeSelectedRoms(filteredRoms.value[i]);
      }
    }
    romsStore.updateLastSelectedRom(selected ? index : index - 1);
  } else {
    romsStore.updateLastSelectedRom(index);
  }
  emitter.emit("refreshSelected");
}

onMounted(async () => {
  fetchRoms(route.params.platform);
});

onBeforeUnmount(() => {
  socket.off("scan:scanning_rom");
  socket.off("scan:done");
  socket.off("scan:done_ko");
  romsStore.reset();
});

onBeforeRouteUpdate(async (to, _) => {
  cursor.value = "";
  searchCursor.value = "";
  roms.value = [];
  searchRoms.value = [];
  filteredRoms.value = [];
  romsStore.reset();
  fetchRoms(to.params.platform);
});
</script>

<template>
  <v-app-bar id="gallery-app-bar" elevation="0" density="compact">
    <filter-bar />
    <gallery-view-btn />
    <v-btn
      @click="scan"
      rounded="0"
      variant="text"
      class="mr-0"
      icon="mdi-magnify-scan"
    />
  </v-app-bar>

  <template v-if="filteredRoms.length > 0">
    <v-row no-gutters v-scroll="onScroll">
      <!-- Gallery cards view -->
      <v-col
        v-show="galleryView.value != 2"
        v-for="rom in filteredRoms"
        class="pa-1"
        :key="rom.id"
        :cols="views[galleryView.value]['size-cols']"
        :xs="views[galleryView.value]['size-xs']"
        :sm="views[galleryView.value]['size-sm']"
        :md="views[galleryView.value]['size-md']"
        :lg="views[galleryView.value]['size-lg']"
      >
        <game-card
          :rom="rom"
          :index="filteredRoms.indexOf(rom)"
          @selectRom="selectRom"
        />
      </v-col>

      <!-- Gallery list view -->
      <v-col v-show="galleryView.value == 2">
        <game-data-table :filteredRoms="filteredRoms" />
      </v-col>
    </v-row>
  </template>

  <!-- Empty gallery message -->
  <template v-if="filteredRoms.length == 0 && !gettingRoms">
    <v-row class="align-center justify-center" no-gutters>
      <v-col cols="6" md="2">
        <div class="mt-16">
          Feels empty here... <v-icon>mdi-emoticon-sad</v-icon>
        </div>
      </v-col>
    </v-row>
  </template>

  <v-layout-item
    v-scroll="onScroll"
    class="text-end"
    :model-value="true"
    position="bottom"
    size="88"
  >
    <div class="ma-4">
      <v-scroll-y-reverse-transition>
        <v-btn
          id="scrollToTop"
          v-show="!scrolledToTop"
          color="primary"
          elevation="8"
          icon
          class="mr-2"
          size="large"
          @click="toTop"
          ><v-icon color="romm-accent-2">mdi-chevron-up</v-icon></v-btn
        >
      </v-scroll-y-reverse-transition>
      <v-menu
        location="top"
        v-model="fabMenu"
        :transition="
          fabMenu ? 'scroll-y-reverse-transition' : 'scroll-y-transition'
        "
      >
        <template v-slot:activator="{ props }">
          <v-fab-transition>
            <v-btn
              v-show="romsStore.selected.length > 0"
              color="romm-accent-1"
              v-bind="props"
              elevation="8"
              icon
              size="large"
              >{{ romsStore.selected.length }}</v-btn
            >
          </v-fab-transition>
        </template>

        <fab-menu :filteredRoms="filteredRoms" />
      </v-menu>
    </div>
  </v-layout-item>

  <search-rom-dialog />
  <edit-rom-dialog />
  <delete-rom-dialog />
  <loading-dialog />
</template>

<style scoped>
#gallery-app-bar {
  z-index: 999 !important;
}
.game-card.game-selected {
  border: 2px solid rgba(var(--v-theme-romm-accent-2));
  padding: 0;
}
#scrollToTop {
  border: 1px solid rgba(var(--v-theme-romm-accent-2));
}
</style>
