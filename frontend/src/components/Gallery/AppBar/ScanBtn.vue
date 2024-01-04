<script setup lang="ts">
import { inject, onBeforeUnmount } from "vue";
import { useRoute } from "vue-router";
import type { Emitter } from "mitt";
import type { Events } from "@/types/emitter";

import socket from "@/services/socket";
import storeScanning from "@/stores/scanning";
import storeRoms from "@/stores/roms";
import storeGalleryFilter from "@/stores/galleryFilter";
import { normalizeString } from "@/utils";

// Props
const emitter = inject<Emitter<Events>>("emitter");
const route = useRoute();
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
    timeout: 4000
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

onBeforeUnmount(() => {
  socket.off("scan:done");
  socket.off("scan:done_ko");
});
</script>

<template>
    <v-btn
      @click="scan"
      rounded="0"
      variant="text"
      class="mr-0"
      icon="mdi-magnify-scan"
    />
</template>
