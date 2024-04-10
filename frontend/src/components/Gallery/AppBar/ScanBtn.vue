<script setup lang="ts">
import socket from "@/services/socket";
import storeHeartbeat from "@/stores/heartbeat";
import storeRoms from "@/stores/roms";
import storeScanning from "@/stores/scanning";
import { computed, ref } from "vue";

// Props
const scanningStore = storeScanning();
const romsStore = storeRoms();
const heartbeat = storeHeartbeat();
// Use a computed property to reactively update metadataOptions based on heartbeat
const metadataOptions = computed(() => [
  {
    name: "IGDB",
    value: "igdb",
    disabled: !heartbeat.value.METADATA_SOURCES?.IGDB_API_ENABLED,
  },
  {
    name: "MobyGames",
    value: "moby",
    disabled: !heartbeat.value.METADATA_SOURCES?.MOBY_API_ENABLED,
  },
]);
// Use the computed metadataOptions to filter out disabled sources
const metadataSources = ref(metadataOptions.value.filter((s) => !s.disabled));

async function scan() {
  scanningStore.set(true);

  if (!socket.connected) socket.connect();

  socket.emit("scan", {
    platforms: [romsStore.platform.id],
    type: "quick",
    apis: metadataSources.value.map((s) => s.value),
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
