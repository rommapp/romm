<script setup lang="ts">
import socket from "@/services/socket";
import storeGalleryFilter from "@/stores/galleryFilter";
import storePlatforms from "@/stores/platforms";
import storeRoms from "@/stores/roms";
import storeScanning from "@/stores/scanning";
import type { Events } from "@/types/emitter";
import { normalizeString } from "@/utils";
import type { Emitter } from "mitt";
import { inject, onBeforeUnmount } from "vue";
import { useRoute } from "vue-router";

// Props
const emitter = inject<Emitter<Events>>("emitter");
const platformsStore = storePlatforms();
const route = useRoute();
const platform = platformsStore.get(Number(route.params.platform));
const scanningStore = storeScanning();
const romsStore = storeRoms();
const galleryFilter = storeGalleryFilter();
const isFiltered = normalizeString(galleryFilter.filter).trim() != "";

// socket.on("scan:scanning_rom", ({ ...rom }) => {
//   romsStore.add([rom]);
//   if (isFiltered) {
//     romsStore.setFiltered(romsStore.filteredRoms);
//   } else {
//     romsStore.setFiltered(romsStore.allRoms);
//   }
// });

async function scan() {
  scanningStore.set(true);

  if (!socket.connected) socket.connect();

  socket.emit("scan", {
    platforms: [platform?.id],
    completeRescan: false,
  });
}

// onBeforeUnmount(() => {
//   socket.off("scan:scanning_rom_s");
//   socket.off("scan:done_s");
//   socket.off("scan:done_ko_s");
// });
</script>

<template>
  <v-list-item v-if="platform" @click="scan" class="py-4 pr-5">
    <v-list-item-title class="d-flex"
      ><v-icon icon="mdi-magnify-scan" class="mr-2" />Scan
      platform</v-list-item-title
    >
  </v-list-item>
</template>
