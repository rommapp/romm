<script setup>
import { ref, inject, onMounted } from "vue";
import { onBeforeRouteUpdate, useRoute } from "vue-router";
import { views } from "@/utils/utils.js";
import { fetchRomsApi } from "@/services/api.js";
import { storeFilter } from "@/stores/filter.js";
import { storeGalleryView } from "@/stores/galleryView.js";
import { normalizeString } from "@/utils/utils.js";
import FilterBar from "@/components/GameGallery/FilterBar.vue";
import GalleryViewBtn from "@/components/GameGallery/GalleryViewBtn.vue";
import GameCard from "@/components/GameGallery/Card/Base.vue";
import GameListHeader from "@/components/GameGallery/ListItem/Header.vue";
import GameListItem from "@/components/GameGallery/ListItem/Item.vue";
import { storeScanning } from "@/stores/scanning.js";
import socket from "@/utils/socket";

import { useDisplay } from "vuetify";
import { downloadRom, downloadSave } from "@/services/download.js";
import { storeDownloading } from "@/stores/downloading.js";
import BackgroundHeader from "@/components/GameDetails/BackgroundHeader.vue";
const { xs, mdAndDown, lgAndUp } = useDisplay();

// Props
const route = useRoute();
// const sections = ['roms', 'firmwares']
const currentSection = ref("roms");
const roms = ref([]);
const gettingRoms = ref(false);
const filter = storeFilter();
const filteredRoms = ref([]);
// const firmwares = ["firmware_base", "firmware_bios"]
const galleryView = storeGalleryView();
const scanning = storeScanning();
const cursor = ref("");
// Event listeners bus
const emitter = inject("emitter");
emitter.on("filter", () => {
  filterRoms();
});

// Functions
async function scan() {
  scanning.set(true);
  emitter.emit("snackbarShow", {
    msg: `Scanning ${route.params.platform}...`,
    icon: "mdi-loading mdi-spin",
    color: "yellow",
  });
  if (!socket.connected) socket.connect();
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
  socket.emit("scan", JSON.stringify([route.params.platform]), false);
}

async function filterRoms() {
  if (filter.value === "") {
    filteredRoms.value = roms.value;
    return;
  }

  gettingRoms.value = true;
  await fetchRomsApi({ platform: route.params.platform, size: 100, searchTerm: filter.value })
    .then((response) => {
      filteredRoms.value = response.data.items;
    })
    .catch((error) => {
      console.error(`Couldn't fetch roms for ${route.params.platform}: ${error}`);
    })
    .finally(() => {
      gettingRoms.value = false;
    });
}

async function fetchMoreRoms(platform) {
  if (cursor.value === null) return;

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

onMounted(async () => {
  fetchMoreRoms(route.params.platform);
});

onBeforeRouteUpdate(async (to, _) => {
  cursor.value = "";
  roms.value = [];
  fetchMoreRoms(to.params.platform);
});
</script>

<template>
  <v-app-bar id="gallery-app-bar" elevation="0" density="compact">
    <!-- <v-select item-title="name" :items="sections" v-model="currentSection" hide-details/> -->
    <filter-bar />
    <gallery-view-btn />
    <v-btn @click="scan" rounded="0" variant="text" class="mr-0" icon="mdi-magnify-scan" />
  </v-app-bar>

  <template v-if="filteredRoms.length > 0 || gettingRoms">
    <v-row v-show="galleryView.value != 2" no-gutters>
      <v-col v-for="rom in filteredRoms" class="pa-1" :key="rom.id" :cols="views[galleryView.value]['size-cols']"
        :xs="views[galleryView.value]['size-xs']" :sm="views[galleryView.value]['size-sm']"
        :md="views[galleryView.value]['size-md']" :lg="views[galleryView.value]['size-lg']">
        <game-card :rom="rom" />
      </v-col>
    </v-row>

    <v-row v-show="galleryView.value == 2" no-gutters>
      <v-col :cols="views[galleryView.value]['size-cols']" :xs="views[galleryView.value]['size-xs']"
        :sm="views[galleryView.value]['size-sm']" :md="views[galleryView.value]['size-md']"
        :lg="views[galleryView.value]['size-lg']">
        <v-table class="bg-secondary">
          <game-list-header />
          <v-divider class="border-opacity-100 mb-4 ml-2 mr-2" color="rommAccent1" :thickness="1" />
          <tbody>
            <v-virtual-scroll :items="filteredRoms" height="calc(100vh - 10.625em)">
              <template v-slot="{ item }">
                <v-list-item :key="item.id" :value="item.id">
                  <game-list-item :rom="item" />
                </v-list-item>
              </template>
            </v-virtual-scroll>
          </tbody>
        </v-table>
      </v-col>
    </v-row>

    <template v-if="gettingRoms">
      <v-row class="justify-center align-center" no-gutters>
        <v-progress-circular color="rommAccent1" :width="3" :size="70" indeterminate />
      </v-row>
    </template>
    <template v-else>
      <v-row class="justify-center align-center" no-gutters>
        <v-btn @click="fetchMoreRoms(route.params.platform)" :disabled="!!filter.value"
          rounded="0" variant="text" class="mr-0" icon>
          <v-icon>mdi-plus</v-icon>
        </v-btn>
      </v-row>
    </template>
  </template>

  <template v-else>
    <v-row class="fill-height justify-center align-center" no-gutters>
      <div class="text-h6">
        Feels empty here... <v-icon>mdi-emoticon-sad</v-icon>
      </div>
    </v-row>
  </template>
</template>

<style scoped>
#gallery-app-bar {
  z-index: 999 !important;
}
</style>
