<script setup>
import { ref, inject, onBeforeUnmount } from "vue";
import socket from "@/services/socket";
import storePlatforms from "@/stores/platforms";
import storeScanning from "@/stores/scanning";
import PlatformIcon from "@/components/Platform/PlatformIcon.vue";

// Props
const platforms = storePlatforms();
const platformsToScan = ref([]);
const scanning = storeScanning();
const scannedPlatforms = ref([]);
const completeRescan = ref(false);

// Event listeners bus
const emitter = inject("emitter");

socket.on("scan:scanning_platform", ({ name, slug }) => {
  scannedPlatforms.value.push({ name, slug, roms: [] });
  window.setTimeout(scrollToBottom, 100);
});

socket.on("scan:scanning_rom", ({ p_slug, p_name, ...rom }) => {
  let platform = scannedPlatforms.value.find((p) => p.slug === p_slug);

  // Add the platform if the socket dropped and it's missing
  if (!platform) {
    scannedPlatforms.value.push({
      name: p_name,
      slug: p_slug,
      roms: [],
    });

    platform = scannedPlatforms.slice(-1);
  }

  platform.roms.push(rom);
  window.setTimeout(scrollToBottom, 100);
});

socket.on("scan:done", () => {
  scanning.set(false);

  emitter.emit("refreshDrawer");
  emitter.emit("refreshView");
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
function scrollToBottom() {
  window.scrollTo(0, document.body.scrollHeight);
}

async function onScan() {
  scanning.set(true);
  scannedPlatforms.value = [];

  if (!socket.connected) socket.connect();

  socket.emit("scan", {
    platforms: platformsToScan.value.map((p) => p.fs_slug),
    rescan: completeRescan.value,
  });
}

onBeforeUnmount(() => {
  socket.off("scan:scanning_platform");
  socket.off("scan:scanning_rom");
  socket.off("scan:done");
  socket.off("scan:done_ko");
});
</script>

<template>
  <!-- Platform selector -->
  <v-row class="pa-4" no-gutters>
    <v-select
      label="Platforms"
      item-title="name"
      v-model="platformsToScan"
      :items="platforms.value"
      variant="outlined"
      density="comfortable"
      multiple
      return-object
      clearable
      hide-details
      rounded="0"
      chips
    />
  </v-row>

  <!-- Complete rescan option -->
  <v-row class="pa-4" no-gutters>
    <v-checkbox
      v-model="completeRescan"
      label="Complete Rescan"
      prepend-icon="mdi-cached"
      hint="Rescan every rom, including already scanned roms"
      persistent-hint
    />
  </v-row>

  <!-- Scan button -->
  <v-row class="pa-4" no-gutters>
    <v-btn
      @click="onScan()"
      :disabled="scanning.value"
      prepend-icon="mdi-magnify-scan"
      rounded="0"
      :loading="scanning.value"
      >Scan
      <template v-slot:loader>
        <v-progress-circular
          color="romm-accent-1"
          :width="2"
          :size="20"
          indeterminate
        />
      </template>
    </v-btn>
  </v-row>

  <v-divider
    class="border-opacity-100 ma-4"
    color="romm-accent-1"
    :thickness="1"
  />

  <!-- Scan log -->
  <v-row
    no-gutters
    class="align-center pa-4"
    v-for="platform in scannedPlatforms"
  >
    <v-col>
      <v-avatar :rounded="0" size="40">
        <platform-icon :platform="platform"></platform-icon>
      </v-avatar>
      <span class="text-body-2 ml-5"> {{ platform.name }}</span>
      <v-list-item v-for="rom in platform.roms" class="text-body-2" disabled>
        <span v-if="rom.r_igdb_id" class="ml-10">
          • Identified <b>{{ rom.r_name }} 👾</b>
        </span>
        <span v-else class="ml-10">
          • {{ rom.file_name }} not found in IGDB
        </span>
      </v-list-item>
    </v-col>
  </v-row>
</template>
