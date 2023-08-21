<script setup>
import { ref, inject, onMounted } from "vue";
import { onBeforeRouteUpdate, useRoute } from "vue-router";
import { fetchRomsApi } from "@/services/api.js";
import socket from "@/services/socket.js";
import { views, normalizeString } from "@/utils/utils.js";
import storeGalleryFilter from "@/stores/galleryFilter.js";
import storeGalleryView from "@/stores/galleryView.js";
import useRomsStore from "@/stores/roms.js";
import storeScanning from "@/stores/scanning.js";
import FilterBar from "@/components/GalleryAppBar/FilterBar.vue";
import GalleryViewBtn from "@/components/GalleryAppBar/GalleryViewBtn.vue";
import GameCard from "@/components/Game/Card/Base.vue";
import GameDataTable from "@/components/Game/DataTable/Base.vue";
import SearchRomDialog from "@/components/Dialog/Rom/SearchRom.vue";
import EditRomDialog from "@/components/Dialog/Rom/EditRom.vue";
import DeleteRomDialog from "@/components/Dialog/Rom/DeleteRom.vue";
import LoadingDialog from "@/components/Dialog/Loading.vue";

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
const romsStore = useRomsStore();
const openedBulkMenu = ref(false);
const scrollOnTop = ref(true);

// Event listeners bus
const emitter = inject("emitter");
emitter.on("filter", onFilterChange);

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
  socket.emit("scan", route.params.platform, false);
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
  scrollOnTop.value = scrollTop == 0; // Check scroll position to show fab to top

  if (cursor.value === null && searchCursor.value === null) return;

  const scrollOffset = 60;

  // If we are close at the bottom of the page, fetch more roms
  if (scrollTop + clientHeight + scrollOffset >= scrollHeight) {
    galleryFilter.value
      ? fetchRoms(route.params.platform)
      : fetchRoms(route.params.platform);
  }
}

function toTop() {
  window.scrollTo({
    top: 0,
    left: 0,
    behavior: "smooth",
  });
}

onMounted(async () => {
  fetchRoms(route.params.platform);
});

onBeforeRouteUpdate(async (to, _) => {
  cursor.value = "";
  searchCursor.value = "";
  roms.value = [];
  searchRoms.value = [];
  filteredRoms.value = [];
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
        <game-card :rom="rom" />
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
          v-show="!scrollOnTop"
          color="primary"
          elevation="8"
          icon="mdi-chevron-up"
          class="mr-2"
          size="large"
          @click="toTop"
        />
      </v-scroll-y-reverse-transition>
      <v-menu
        location="top"
        v-model="openedBulkMenu"
        :transition="
          openedBulkMenu ? 'scroll-y-reverse-transition' : 'scroll-y-transition'
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
              @click=""
              >{{ romsStore.selected.length }}</v-btn
            >
          </v-fab-transition>
        </template>

        <v-btn
          v-show="romsStore.selected.length > 0"
          color="terciary"
          elevation="8"
          icon="mdi-delete"
          size="large"
          class="mb-2"
          @click=""
          ><v-icon color="romm-red">mdi-delete</v-icon></v-btn
        >
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
</style>
