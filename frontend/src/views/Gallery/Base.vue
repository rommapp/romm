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
import SearchRomDialog from "@/components/Dialog/Rom/SearchRom.vue";
import EditRomDialog from "@/components/Dialog/Rom/EditRom.vue";
import DeleteRomDialog from "@/components/Dialog/Rom/DeleteRom.vue";
import LoadingDialog from "@/components/Dialog/Loading.vue";

import { VDataTable } from "vuetify/labs/VDataTable";
import { downloadRomApi } from "@/services/api.js";
import useDownloadStore from "@/stores/download.js";
import AdminMenu from "@/components/AdminMenu/Base.vue";
const location = window.location.origin;
const downloadStore = useDownloadStore();
const saveFiles = ref(false);
const romsPerPage = ref(-1);
const romsPerPageOptions = [
  { value: -1, title: "$vuetify.dataFooter.itemsPerPageAll" },
];
const romsHeaders = [
  {
    title: "",
    align: "start",
    sortable: false,
    key: "path_cover_s",
  },
  {
    title: "Name",
    align: "start",
    sortable: true,
    key: "r_name",
  },
  {
    title: "File",
    align: "start",
    sortable: true,
    key: "file_name",
  },
  {
    title: "Size",
    align: "start",
    sortable: true,
    key: "file_size",
  },
  {
    title: "Reg",
    align: "start",
    sortable: true,
    key: "region",
  },
  {
    title: "Rev",
    align: "start",
    sortable: true,
    key: "revision",
  },
  { align: "end", key: "actions", sortable: false },
];

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
  emitter.emit("snackbarShow", {
    msg: "Scan completed successfully!",
    icon: "mdi-check-bold",
    color: "green",
  });
  socket.disconnect();
  emitter.emit("refreshPlatforms");
  emitter.emit("refreshGallery");
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
  socket.emit("scan", route.params.platform, false);
}

async function fetchMoreSearch() {
  if (searchCursor.value === null || gettingRoms.value) return;

  gettingRoms.value = true;
  emitter.emit("showLoadingDialog", {
    loading: gettingRoms.value,
    scrim: false,
  });
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
      emitter.emit("showLoadingDialog", {
        loading: gettingRoms.value,
        scrim: false,
      });
    });
}

async function fetchMoreRoms(platform) {
  if (cursor.value === null || gettingRoms.value) return;

  gettingRoms.value = true;
  emitter.emit("showLoadingDialog", {
    loading: gettingRoms.value,
    scrim: false,
  });
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

  <template v-if="filteredRoms.length > 0">
    <!-- Gallery cards view -->
    <v-row v-show="galleryView.value != 2" no-gutters v-scroll="onGridScroll">
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
      <!-- <v-col
        :cols="views[galleryView.value]['size-cols']"
        :xs="views[galleryView.value]['size-xs']"
        :sm="views[galleryView.value]['size-sm']"
        :md="views[galleryView.value]['size-md']"
        :lg="views[galleryView.value]['size-lg']"
      >
        <v-table class="bg-secondary">
          <game-list-header />
          <v-divider
            class="border-opacity-100 my-4 mx-2"
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
      </v-col> -->
      <v-data-table
        :items-per-page="romsPerPage"
        :items-per-page-options="romsPerPageOptions"
        items-per-page-text=""
        :headers="romsHeaders"
        item-value="id"
        :items="filteredRoms"
      >
        <template v-slot:item.path_cover_s="{ item }">
          <v-avatar :rounded="0">
            <v-progress-linear
              color="rommAccent1"
              :active="downloadStore.value.includes(item.selectable.id)"
              :indeterminate="true"
              absolute
            />
            <v-img
              :src="`/assets/romm/resources/${item.selectable.path_cover_s}`"
              :lazy-src="`/assets/romm/resources/${item.selectable.path_cover_s}`"
              min-height="150"
            />
          </v-avatar>
        </template>
        <template v-slot:item.file_size="{ item }">
          <span
            >{{ item.selectable.file_size }}
            {{ item.selectable.file_size_units }}</span
          >
        </template>
        <template v-slot:item.actions="{ item }">
          <template v-if="item.selectable.multi">
            <v-btn
              class="my-1"
              @click="downloadRomApi(item.selectable)"
              :disabled="downloadStore.value.includes(item.selectable.id)"
              download
              size="small"
              variant="text"
              ><v-icon>mdi-download</v-icon></v-btn
            >
          </template>
          <template v-else>
            <v-btn
              class="my-1"
              :href="`${location}${item.selectable.download_path}`"
              download
              size="small"
              variant="text"
              ><v-icon>mdi-download</v-icon></v-btn
            >
          </template>
          <v-btn size="small" variant="text" :disabled="!saveFiles" class="my-1"
            ><v-icon>mdi-content-save-all</v-icon></v-btn
          >
          <v-menu location="bottom">
            <template v-slot:activator="{ props }">
              <v-btn
                @click=""
                v-bind="props"
                size="small"
                variant="text"
                class="my-1"
                ><v-icon>mdi-dots-vertical</v-icon></v-btn
              >
            </template>
            <admin-menu :rom="item.selectable" />
          </v-menu>
        </template>
      </v-data-table>
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

  <search-rom-dialog />
  <edit-rom-dialog />
  <delete-rom-dialog />
  <loading-dialog />
</template>

<style scoped>
#gallery-app-bar {
  z-index: 999 !important;
}
</style>
