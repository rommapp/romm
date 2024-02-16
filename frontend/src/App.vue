<script setup lang="ts">
import Notification from "@/components/Notification.vue";
import api from "@/services/api/index";
import storeConfig from "@/stores/config";
import storeHeartbeat from "@/stores/heartbeat";
import socket from "@/services/socket";
import { onBeforeMount } from "vue";
import cookie from "js-cookie";
import storeGalleryFilter from "@/stores/galleryFilter";
import storeRoms, { type Rom } from "@/stores/roms";
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
const heartbeatStore = storeHeartbeat();
const configStore = storeConfig();

socket.on(
  "scan:scanning_platform",
  ({ name, slug, id }: { name: string; slug: string; id: number }) => {
    scanningStore.set(true);
    scanningPlatforms.value.push({ name, slug, id, roms: [] });
  }
);

socket.on("scan:scanning_rom", (rom: Rom) => {
  scanningStore.set(true);
  if (romsStore.platform.name === rom.platform_name) {
    romsStore.add([rom]);
    romsStore.setFiltered(
      isFiltered ? romsStore.filteredRoms : romsStore.allRoms,
      galleryFilter
    );
  }

  let scannedPlatform = scanningPlatforms.value.find(
    (p) => p.slug === rom.platform_slug
  );

  // Add the platform if the socket dropped and it's missing
  if (!scannedPlatform) {
    scanningPlatforms.value.push({
      name: rom.platform_name,
      slug: rom.platform_slug,
      id: rom.platform_id,
      roms: [],
    });
    scannedPlatform = scanningPlatforms.value[0];
  }

  scannedPlatform?.roms.push(rom);
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

onBeforeMount(() => {
  api.get("/heartbeat").then(({ data: heartBeatData }) => {
    heartbeatStore.set(heartBeatData);
  });
  api.get("/config").then(({ data: configData }) => {
    configStore.set(configData);
  });
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
