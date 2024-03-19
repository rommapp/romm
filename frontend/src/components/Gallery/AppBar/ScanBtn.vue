<script setup lang="ts">
import socket from "@/services/socket";
import storeRoms from "@/stores/roms";
import storeScanning from "@/stores/scanning";

// Props
const scanningStore = storeScanning();
const romsStore = storeRoms();

async function scan() {
  scanningStore.set(true);

  if (!socket.connected) socket.connect();

  socket.emit("scan", {
    platforms: [romsStore.platform.id],
    type: "unidentified",
  });
}
</script>

<template>
  <v-list-item v-if="romsStore.platform" @click="scan" class="py-4 pr-5">
    <v-list-item-title class="d-flex">
      <v-icon icon="mdi-magnify-scan" class="mr-2" />
      Scan platform
    </v-list-item-title>
  </v-list-item>
</template>
