<script setup lang="ts">
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { inject } from "vue";
import { useRoute } from "vue-router";

import romApi from "@/services/api/rom";
import socket from "@/services/socket";
import storeAuth from "@/stores/auth";
import storeRoms from "@/stores/roms";
import storeScanning from "@/stores/scanning";

// Event listeners bus
const emitter = inject<Emitter<Events>>("emitter");

// Props
const auth = storeAuth();
const romsStore = storeRoms();
const scanningStore = storeScanning();
const route = useRoute();

// Functions
async function onScan() {
  scanningStore.set(true);
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

function selectAllRoms() {
  if (romsStore.filteredRoms.length === romsStore.selectedRoms.length) {
    romsStore.resetSelection();
    emitter?.emit("openFabMenu", false);
  } else {
    romsStore.setSelection(romsStore.filteredRoms);
  }
}

function onDownload() {
  romsStore.selectedRoms.forEach((rom) => {
    romApi.downloadRom({ rom });
  });
}
</script>

<template>
  <v-btn
    color="terciary"
    elevation="8"
    :icon="
      romsStore.filteredRoms.length === romsStore.selectedRoms.length
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
    @click="emitter?.emit('showDeleteRomDialog', romsStore.selectedRoms)"
  >
    <v-icon color="romm-red">mdi-delete</v-icon>
  </v-btn>
</template>
