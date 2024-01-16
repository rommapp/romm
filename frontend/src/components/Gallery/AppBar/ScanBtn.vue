<script setup lang="ts">
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { inject, onBeforeUnmount } from "vue";
import { useRoute } from "vue-router";

import socket from "@/services/socket";
import storeGalleryFilter from "@/stores/galleryFilter";
import storePlatforms from "@/stores/platforms";
import storeRoms from "@/stores/roms";
import storeScanning from "@/stores/scanning";
import { normalizeString } from "@/utils";

// Props
const emitter = inject<Emitter<Events>>("emitter");
const platformsStore = storePlatforms();
const route = useRoute();
const platform = platformsStore.get(Number(route.params.platform));
const scanning = storeScanning();
const romsStore = storeRoms();
const galleryFilter = storeGalleryFilter();
const isFiltered = normalizeString(galleryFilter.filter).trim() != "";

socket.on("scan:scanning_rom", (rom) => {
  romsStore.add([rom]);
  if (isFiltered) {
    romsStore.setFiltered(romsStore.filteredRoms);
  } else {
    romsStore.setFiltered(romsStore.allRoms);
  }
});

// Functions
socket.on("scan:done", () => {
  scanning.set(false);
  socket.disconnect();
  emitter?.emit("refreshDrawer", null);
  emitter?.emit("snackbarShow", {
    msg: "Scan completed successfully!",
    icon: "mdi-check-bold",
    color: "green",
    timeout: 4000,
  });
});

socket.on("scan:done_ko", (msg) => {
  scanning.set(false);
  emitter?.emit("snackbarShow", {
    msg: `Scan couldn't be completed. Something went wrong: ${msg}`,
    icon: "mdi-close-circle",
    color: "red",
  });
  socket.disconnect();
});

async function scan() {
  scanning.set(true);
  emitter?.emit("snackbarShow", {
    msg: `Scanning ${platform?.name}...`,
    icon: "mdi-loading mdi-spin",
    color: "romm-accent-1",
  });

  if (!socket.connected) socket.connect();
  socket.emit("scan", {
    platforms: [platform?.id],
    rescan: false,
  });
}

onBeforeUnmount(() => {
  socket.off("scan:done");
  socket.off("scan:done_ko");
});
</script>

<template>
  <v-list-item v-if="platform" @click="scan" class="py-4 pr-5">
    <v-list-item-title class="d-flex"
      ><v-icon icon="mdi-magnify-scan" class="mr-2" />Scan
      platform</v-list-item-title
    >
  </v-list-item>
</template>
