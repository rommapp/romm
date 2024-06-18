<script setup lang="ts">
import socket from "@/services/socket";
import storeHeartbeat from "@/stores/heartbeat";
import storeRoms from "@/stores/roms";
import storeScanning from "@/stores/scanning";

// Props
const scanningStore = storeScanning();
const romsStore = storeRoms();
const heartbeat = storeHeartbeat();

async function scan() {
  scanningStore.set(true);

  if (!socket.connected) socket.connect();

  socket.emit("scan", {
    platforms: [romsStore.currentPlatform?.id],
    type: "quick",
    apis: heartbeat.getMetadataOptions().map((s) => s.value),
  });
}
</script>

<template>
  <v-list-item v-if="romsStore.currentPlatform?.id" class="py-4 pr-5" @click="scan">
    <v-list-item-title class="d-flex">
      <v-icon icon="mdi-magnify-scan" class="mr-2" />
      Scan platform
    </v-list-item-title>
  </v-list-item>
</template>
