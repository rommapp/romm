<script setup lang="ts">
import Notification from "@/components/Notification.vue";
import api from "@/services/api/index";
import storeAuth from "@/stores/auth";
import storeConfig from "@/stores/config";
import storeHeartbeat from "@/stores/heartbeat";
import socket from "@/services/socket";
import { onBeforeMount } from "vue";
import cookie from "js-cookie";
import storeGalleryFilter from "@/stores/galleryFilter";
import storeRoms from "@/stores/roms";
import storeScanning from "@/stores/scanning";
import type { Events } from "@/types/emitter";
import { normalizeString } from "@/utils";
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import { inject, onBeforeUnmount } from "vue";

// Props
const scanningStore = storeScanning();
const { scanningPlatforms } = storeToRefs(scanningStore);
const romsStore = storeRoms();
const galleryFilter = storeGalleryFilter();
const isFiltered = normalizeString(galleryFilter.filterSearch).trim() != "";
const emitter = inject<Emitter<Events>>("emitter");

// Props
const authStore = storeAuth();
const heartbeatStore = storeHeartbeat();
const configStore = storeConfig();

function scrollToBottom() {
  window.scrollTo(0, document.body.scrollHeight);
}

socket.on("scan:scanning_platform", ({ name, slug, id }) => {
  scanningPlatforms.value.push({ name, slug, id, roms: [] });
  window.setTimeout(scrollToBottom, 100);
});

socket.on("scan:scanning_rom", ({ platform_name, platform_slug, ...rom }) => {
  romsStore.add([rom]);
  if (isFiltered) {
    romsStore.setFiltered(
      romsStore.filteredRoms,
      galleryFilter.filterUnmatched,
      galleryFilter.selectedGenre,
      galleryFilter.selectedFranchise,
      galleryFilter.selectedCollection,
      galleryFilter.selectedCompany
    );
  } else {
    romsStore.setFiltered(
      romsStore.allRoms,
      galleryFilter.filterUnmatched,
      galleryFilter.selectedGenre,
      galleryFilter.selectedFranchise,
      galleryFilter.selectedCollection,
      galleryFilter.selectedCompany
    );
  }

  let scannedPlatform = scanningPlatforms.value.find(
    (p) => p.slug === platform_slug
  );

  // Add the platform if the socket dropped and it's missing
  if (scannedPlatform) {
    scanningPlatforms.value.push(scannedPlatform);
    scannedPlatform = scanningPlatforms.value.pop();
  }

  scannedPlatform?.roms.push(rom);
  window.setTimeout(scrollToBottom, 100);
});

socket.on("scan:done", () => {
  scanningStore.set(false);
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
  scanningStore.set(false);

  emitter?.emit("snackbarShow", {
    msg: `Scan couldn't be completed. Something went wrong: ${msg}`,
    icon: "mdi-close-circle",
    color: "red",
  });
  socket.disconnect();
});

onBeforeUnmount(() => {
  socket.off("scan:scanning_platform");
  socket.off("scan:scanning_rom");
  socket.off("scan:done");
  socket.off("scan:done_ko");
});

onBeforeMount(async () => {
  const { data: heartBeatData } = await api.get("/heartbeat");
  heartbeatStore.set(heartBeatData);
  authStore.setEnabled(heartBeatData.ROMM_AUTH_ENABLED ?? false);
  const { data: configData } = await api.get("/config");
  configStore.set(configData);
  // Set CSRF token for all requests
  api.defaults.headers.common["x-csrftoken"] = cookie.get("csrftoken");
});
</script>

<template>
  <v-app>
    <v-main>
      <notification class="mt-6" />
      <router-view />
    </v-main>
  </v-app>
</template>
<style>
body {
  background-color: rgba(var(--v-theme-background));
}
</style>
