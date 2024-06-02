<script setup lang="ts">
import { inject } from "vue";
import type { Emitter } from "mitt";
import { useRoute } from "vue-router";
import romApi from "@/services/api/rom";
import socket from "@/services/socket";
import storeAuth from "@/stores/auth";
import storeHeartbeat from "@/stores/heartbeat";
import storeRoms from "@/stores/roms";
import storeScanning from "@/stores/scanning";
import type { Events } from "@/types/emitter";

// Event listeners bus
const emitter = inject<Emitter<Events>>("emitter");

// Props
const auth = storeAuth();
const romsStore = storeRoms();
const scanningStore = storeScanning();
const route = useRoute();
const heartbeat = storeHeartbeat();

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
    roms: romsStore.selectedRoms,
    type: "partial",
    apis: heartbeat.getMetadataOptions().map((s) => s.value),
  });
}

function selectAllRoms() {
  romsStore.setSelection(romsStore.filteredRoms);
}

function resetSelection() {
  romsStore.resetSelection();
  emitter?.emit("openFabMenu", false);
}

function onDownload() {
  romsStore.selectedRoms.forEach((rom) => {
    romApi.downloadRom({ rom });
  });
}
</script>

<template>
  <v-tooltip
    open-delay="500"
    class="tooltip"
    text="Reset selection"
    location="top"
  >
    <template #activator="{ props }">
      <v-btn
        v-bind="props"
        color="terciary"
        elevation="8"
        icon="mdi-select"
        class="mb-2 ml-1"
        @click.stop="resetSelection"
      />
    </template>
  </v-tooltip>

  <v-tooltip
    open-delay="500"
    class="tooltip"
    text="Select all"
    location="top"
  >
    <template #activator="{ props }">
      <v-btn
        v-bind="props"
        color="terciary"
        elevation="8"
        icon="mdi-select-all"
        class="mb-2 ml-1"
        @click.stop="selectAllRoms"
      />
    </template>
  </v-tooltip>

  <v-tooltip
    open-delay="500"
    class="tooltip"
    text="Scan selected games"
    location="top"
  >
    <template #activator="{ props }">
      <v-btn
        v-if="auth.scopes.includes('roms.write')"
        v-bind="props"
        color="terciary"
        elevation="8"
        icon
        class="mb-2 ml-1"
        @click="onScan"
      >
        <v-icon>mdi-magnify-scan</v-icon>
      </v-btn>
    </template>
  </v-tooltip>

  <v-tooltip
    open-delay="500"
    class="tooltip"
    text="Download selected games"
    location="top"
  >
    <template #activator="{ props }">
      <v-btn
        v-bind="props"
        color="terciary"
        elevation="8"
        icon
        class="mb-2 ml-1"
        @click="onDownload"
      >
        <v-icon>mdi-download</v-icon>
      </v-btn>
    </template>
  </v-tooltip>

  <v-tooltip
    open-delay="500"
    class="tooltip"
    text="Delete selected games"
    location="top"
  >
    <template #activator="{ props }">
      <v-btn
        v-if="auth.scopes.includes('roms.write')"
        v-bind="props"
        color="terciary"
        elevation="8"
        icon
        class="mb-3 ml-1"
        @click="emitter?.emit('showDeleteRomDialog', romsStore.selectedRoms)"
      >
        <v-icon color="romm-red">
          mdi-delete
        </v-icon>
      </v-btn>
    </template>
  </v-tooltip>
</template>

<style scoped>
.tooltip :deep(.v-overlay__content) {
  background: rgba(201, 201, 201, 0.98) !important;
  color: rgb(41, 41, 41) !important;
}
</style>
