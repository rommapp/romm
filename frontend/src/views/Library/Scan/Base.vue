<script setup lang="ts">
import PlatformIcon from "@/components/Platform/PlatformIcon.vue";
import socket from "@/services/socket";
import storePlatforms, { type Platform } from "@/stores/platforms";
import storeScanning from "@/stores/scanning";
import { storeToRefs } from "pinia";
import { ref } from "vue";

// Props
const scanningStore = storeScanning();
const { scanning, scanningPlatforms } = storeToRefs(scanningStore);
const completeRescan = ref(false);
const rescanUnidentified = ref(false);
const platforms = storePlatforms();
const platformsToScan = ref<Platform[]>([]);

// Connect to socket on load to catch running scans
if (!socket.connected) socket.connect();

async function scan() {
  scanningStore.set(true);
  scanningPlatforms.value = [];

  if (!socket.connected) socket.connect();

  socket.emit("scan", {
    platforms: platformsToScan.value.map((p) => p.id),
    completeRescan: completeRescan.value,
    rescanUnidentified: rescanUnidentified.value,
  });
}
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

  <v-row class="pa-4" no-gutters>
    <!-- Complete rescan option -->
    <v-col cols="12" xs="12" sm="6" md="4" lg="4" xl="4">
      <v-checkbox
        v-model="completeRescan"
        label="Complete Rescan"
        prepend-icon="mdi-cached"
        hint="Rescan every rom, including already scanned roms"
        persistent-hint
      />
    </v-col>

    <!-- Rescan unidentified option -->
    <v-col cols="12" xs="12" sm="6" md="4" lg="4" xl="4">
      <v-checkbox
        v-model="rescanUnidentified"
        label="Rescan Unidentified"
        prepend-icon="mdi-file-search-outline"
        hint="Rescan only unidentified games"
        persistent-hint
      />
    </v-col>
  </v-row>

  <!-- Scan button -->
  <v-row class="pa-4" no-gutters>
    <v-btn
      @click="scan()"
      :disabled="scanning"
      prepend-icon="mdi-magnify-scan"
      rounded="0"
      :loading="scanning"
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
    v-for="platform in scanningPlatforms"
  >
    <v-col>
      <v-list-item
        :to="{ name: 'platform', params: { platform: platform.id } }"
      >
        <v-avatar :rounded="0" size="40">
          <platform-icon :key="platform.slug" :slug="platform.slug" />
        </v-avatar>
        <span class="text-body-2 ml-5"> {{ platform.name }}</span>
      </v-list-item>
      <v-list-item
        v-for="rom in platform.roms"
        class="text-body-2 romm-grey"
        :to="{ name: 'rom', params: { rom: rom.id } }"
      >
        <span v-if="rom.igdb_id || rom.moby_id" class="ml-10">
          • Identified <b>{{ rom.name }} 👾</b>
        </span>
        <span v-else class="ml-10">
          • {{ rom.file_name }} not found ❌
        </span>
      </v-list-item>
    </v-col>
  </v-row>
</template>
