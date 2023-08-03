<script setup>
import { ref, inject, onMounted } from "vue";
import { onBeforeRouteUpdate, useRoute } from "vue-router";
import { fetchRomsApi } from "@/services/api.js";
import socket from "@/services/socket.js";
import { views, normalizeString } from "@/utils/utils.js";
import storeGalleryFilter from "@/stores/galleryFilter.js";
import storeGalleryView from "@/stores/galleryView.js";
import storeScanning from "@/stores/scanning.js";
import FilterBar from "@/components/GalleryAppBar/FilterBar.vue";
import GalleryViewBtn from "@/components/GalleryAppBar/GalleryViewBtn.vue";
import GameCard from "@/components/Game/Card/Base.vue";
import GameListHeader from "@/components/Game/ListItem/Header.vue";
import GameListItem from "@/components/Game/ListItem/Item.vue";

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

// Event listeners bus
const emitter = inject("emitter");
emitter.on("filter", onFilterChange);

socket.on("scan:done", () => {
  scanning.set(false);
  emitter.emit("refreshGallery");
  emitter.emit("snackbarShow", {
    msg: "Scan completed successfully!",
    icon: "mdi-check-bold",
    color: "green",
  });
  socket.disconnect();
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
    color: "rommAccent1",
  });

  if (!socket.connected) socket.connect();
  socket.emit("scan", JSON.stringify([route.params.platform]), false);
}

async function fetchMoreSearch() {
  if (searchCursor.value === null || gettingRoms.value) return;

  gettingRoms.value = true;
  await fetchRomsApi({
    platform: route.params.platform,
    cursor: searchCursor.value,
    searchTerm: normalizeString(galleryFilter.value),
  })
    .then((response) => {
      searchRoms.value = [...searchRoms.value, ...response.data.items];
      filteredRoms.value = searchRoms.value;
      searchCursor.value = response.data.next_page;
    })
    .catch((error) => {
      console.error(
        `Couldn't fetch roms for ${route.params.platform}: ${error}`
      );
    })
    .finally(() => {
      gettingRoms.value = false;
    });
}

async function fetchMoreRoms(platform) {
  if (cursor.value === null || gettingRoms.value) return;

  gettingRoms.value = true;
  await fetchRomsApi({ platform, cursor: cursor.value })
    .then((response) => {
      roms.value = [...roms.value, ...response.data.items];
      filteredRoms.value = roms.value;
      cursor.value = response.data.next_page;
    })
    .catch((error) => {
      console.error(`Couldn't fetch roms for ${platform}: ${error}`);
    })
    .finally(() => {
      gettingRoms.value = false;
    });
}

function onFilterChange() {
  searchCursor.value = "";
  searchRoms.value = [];

  if (galleryFilter.value === "") {
    filteredRoms.value = roms.value;
    return;
  }

  fetchMoreSearch();
}

function onGridScroll() {
  if (cursor.value === null && searchCursor.value === null) return;

  const { scrollTop, scrollHeight, clientHeight } = document.documentElement;
  const scrollOffset = 60;

  // If we are close at the bottom of the page, fetch more roms
  if (scrollTop + clientHeight + scrollOffset >= scrollHeight) {
    galleryFilter.value
      ? fetchMoreSearch()
      : fetchMoreRoms(route.params.platform);
  }
}

onMounted(async () => {
  fetchMoreRoms(route.params.platform);
});

onBeforeRouteUpdate(async (to, _) => {
  cursor.value = "";
  searchCursor.value = "";

  roms.value = [];
  searchRoms.value = [];
  filteredRoms.value = [];

  fetchMoreRoms(to.params.platform);
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

  <template v-if="filteredRoms.length > 0 || gettingRoms">
    <!-- Gallery cards view -->
    <v-row
      id="grid-view"
      v-show="galleryView.value != 2"
      no-gutters
      v-scroll="onGridScroll"
    >
      <v-col
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
    </v-row>

    <!-- Gallery list view -->
    <v-row v-show="galleryView.value == 2" no-gutters>
      <v-col
        :cols="views[galleryView.value]['size-cols']"
        :xs="views[galleryView.value]['size-xs']"
        :sm="views[galleryView.value]['size-sm']"
        :md="views[galleryView.value]['size-md']"
        :lg="views[galleryView.value]['size-lg']"
      >
        <v-table class="bg-secondary">
          <game-list-header />
          <v-divider
            class="border-opacity-100 mb-4 ml-2 mr-2"
            color="rommAccent1"
            :thickness="1"
          />
          <tbody>
            <v-list class="bg-secondary">
              <v-list-item
                v-for="item in filteredRoms"
                :key="item.id"
                :value="item.id"
              >
                <game-list-item :rom="item" />
              </v-list-item>
            </v-list>
          </tbody>
        </v-table>
      </v-col>
    </v-row>
  </template>

  <!-- Empty gallery message -->
  <template v-else>
    <v-row class="fill-height justify-center align-center" no-gutters>
      <div class="text-h6">
        Feels empty here... <v-icon>mdi-emoticon-sad</v-icon>
      </div>
    </v-row>
  </template>

  <template v-if="gettingRoms">
    <v-dialog
      :model-value="gettingRoms"
      scroll-strategy="none"
      width="auto"
      :scrim="false"
      persistent
    >
      <v-progress-circular
        :width="3"
        :size="70"
        color="rommAccent1"
        indeterminate
      />
    </v-dialog>
  </template>
</template>

<style scoped>
#gallery-app-bar {
  z-index: 999 !important;
}
</style>
