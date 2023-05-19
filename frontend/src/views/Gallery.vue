<script setup>
import { ref, inject, onMounted } from "vue";
import { onBeforeRouteUpdate, useRoute } from "vue-router";
import { fetchRomsApi } from "@/services/api.js";
import { socket } from "@/services/socket.js";
import { views, normalizeString } from "@/utils/utils.js";
import { storeGalleryFilter } from "@/stores/galleryFilter.js";
import { storeGalleryView } from "@/stores/galleryView.js";
import { storeScanning } from "@/stores/scanning.js";
import FilterBar from "@/components/GalleryAppBar/FilterBar.vue";
import GalleryViewBtn from "@/components/GalleryAppBar/GalleryViewBtn.vue";
import GameCard from "@/components/Game/Card/Base.vue";
import GameListHeader from "@/components/Game/ListItem/Header.vue";
import GameListItem from "@/components/Game/ListItem/Item.vue";

// Props
const route = useRoute();
const roms = ref([]);
const romsFiltered = ref([]);
const galleryFilter = storeGalleryFilter();
const galleryView = storeGalleryView();
const gettingRoms = ref(false);
const scanning = storeScanning();

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
    color: "rommAccent1",
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

function filterRoms() {
  romsFiltered.value = roms.value.filter((rom) => {
    return normalizeString(rom.file_name).includes(galleryFilter.value);
  });
}

async function fetchRoms(platform) {
  gettingRoms.value = true;
  await fetchRomsApi(platform)
    .then((response) => {
      roms.value = response.data.data;
      filterRoms();
    })
    .catch((error) => {
      console.log(error);
      console.log(`Couldn't fetch roms for ${platform}`);
    })
    .finally(() => {
      gettingRoms.value = false;
    });
}

onMounted(async () => {
  fetchRoms(route.params.platform);
});
onBeforeRouteUpdate(async (to, _) => {
  fetchRoms(to.params.platform);
});
</script>

<template>
  <v-app-bar id="gallery-app-bar" elevation="0" density="compact">
    <!-- <v-select item-title="name" :items="sections" v-model="currentSection" hide-details/> -->
    <filter-bar />
    <gallery-view-btn />
    <v-btn @click="scan" rounded="0" variant="text" class="mr-0" icon="mdi-magnify-scan" />
  </v-app-bar>

  <template v-if="gettingRoms">
    <!-- Gallery loader -->
    <v-row class="fill-height justify-center align-center" no-gutters>
      <v-progress-circular color="rommAccent1" :width="3" :size="70" indeterminate />
    </v-row>
  </template>
  <template v-else>
    <template v-if="roms.length > 0">
      <!-- Gallery cards view -->
      <v-row v-show="galleryView.value != 2" id="card-view" no-gutters>
        <v-col v-for="rom in romsFiltered" class="pa-1" :key="rom.file_name" :cols="views[galleryView.value]['size-cols']"
          :xs="views[galleryView.value]['size-xs']" :sm="views[galleryView.value]['size-sm']"
          :md="views[galleryView.value]['size-md']" :lg="views[galleryView.value]['size-lg']">
          <game-card :rom="rom" />
        </v-col>
      </v-row>

      <!-- Gallery list view -->
      <v-row v-show="galleryView.value == 2" id="list-view" no-gutters>
        <v-col :cols="views[galleryView.value]['size-cols']" :xs="views[galleryView.value]['size-xs']"
          :sm="views[galleryView.value]['size-sm']" :md="views[galleryView.value]['size-md']"
          :lg="views[galleryView.value]['size-lg']">
          <v-table class="bg-secondary">
            <game-list-header />
            <v-divider class="border-opacity-100 mb-4 ml-2 mr-2" color="rommAccent1" :thickness="1" />
            <tbody>
              <game-list-item v-for="rom in romsFiltered" :key="rom.file_name" :rom="rom" />
            </tbody>
          </v-table>
        </v-col>
      </v-row>
    </template>

    <!-- Empty gallery message -->
    <template v-else>
      <v-row class="fill-height justify-center align-center" no-gutters>
        <div class="text-h6">
          Feels cold here... <v-icon>mdi-emoticon-sad</v-icon>
        </div>
      </v-row>
    </template>
  </template>
</template>

<style scoped>
#gallery-app-bar {
  z-index: 999 !important;
}
</style>
