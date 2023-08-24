<script setup>
import { inject } from "vue";
import { useRoute } from "vue-router";
import storeAuth from "@/stores/auth";
import storeRoms from "@/stores/roms";
import socket from "@/services/socket";
import storeScanning from "@/stores/scanning";
import { downloadRomApi } from "@/services/api";

// Event listeners bus
const emitter = inject("emitter");

// Props
const props = defineProps(["filteredRoms"]);
const auth = storeAuth();
const romsStore = storeRoms();
const scanning = storeScanning();
const route = useRoute();

socket.on("scan:scanning_rom", ({ id }) => {
  const rom = romsStore.selected.find((r) => r.id === id);
  romsStore.removeSelectedRoms(rom);
});

socket.on("scan:done", () => {
  scanning.set(false);
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

// Functions
async function onScan() {
  scanning.set(true);
  emitter.emit("snackbarShow", {
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

function selectAllRoms() {
  if (props.filteredRoms.length === romsStore.selected.length) {
    romsStore.reset();
    emitter.emit("openFabMenu", false);
  } else {
    romsStore.updateSelectedRoms(props.filteredRoms);
  }
  emitter.emit("refreshSelected");
}

function onDownload() {
  romsStore.selected.forEach((rom) => {
    downloadRomApi(rom);
  });
}
</script>

<template>
  <v-btn
    color="terciary"
    elevation="8"
    :icon="
      filteredRoms.length === romsStore.selected.length
        ? 'mdi-select'
        : 'mdi-select-all'
    "
    class="mb-2 ml-1"
    @click.stop="selectAllRoms"
  />

  <v-btn
    v-if="auth.scopes.includes('roms.write')"
    color="terciary"
    elevation="8"
    icon
    class="mb-2 ml-1"
    @click="onScan"
  >
    <v-icon>mdi-magnify-scan</v-icon>
  </v-btn>

  <v-btn
    color="terciary"
    elevation="8"
    icon
    class="mb-2 ml-1"
    @click="onDownload"
  >
    <v-icon>mdi-download</v-icon>
  </v-btn>

  <v-btn
    v-if="auth.scopes.includes('roms.write')"
    color="terciary"
    elevation="8"
    icon
    class="mb-3 ml-1"
    @click="emitter.emit('showDeleteRomDialog', romsStore.selected)"
  >
    <v-icon color="romm-red">mdi-delete</v-icon>
  </v-btn>
</template>
