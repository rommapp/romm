<script setup lang="ts">
import PlatformIcon from "@/components/Platform/PlatformIcon.vue";
import socket from "@/services/socket";
import storeHeartbeat from "@/stores/heartbeat";
import storePlatforms, { type Platform } from "@/stores/platforms";
import storeScanning from "@/stores/scanning";
import { storeToRefs } from "pinia";
import { ref } from "vue";

// Props
const scanningStore = storeScanning();
const { scanning, scanningPlatforms, scanStats } = storeToRefs(scanningStore);
const platforms = storePlatforms();
const heartbeat = storeHeartbeat();

const scanOptions = [
  {
    title: "New platforms",
    subtitle: "Scan new platforms only (fastest)",
    value: "new_platforms",
  },
  {
    title: "Quick scan",
    subtitle: "Scan new files only",
    value: "quick",
  },
  {
    title: "Unidentified games",
    subtitle: "Scan games with no metadata match",
    value: "unidentified",
  },
  {
    title: "Partial metadata",
    subtitle: "Scan games with partial metadata matches",
    value: "partial",
  },
  {
    title: "Complete rescan",
    subtitle: "Total rescan of all platforms and files (slowest)",
    value: "complete",
  },
];

const metadataOptions = [
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
];

const platformsToScan = ref<Platform[]>([]);
const scanType = ref("quick");
const metadataSources = ref<typeof metadataOptions>(
  metadataOptions.filter((s) => !s.disabled)
);

// Connect to socket on load to catch running scans
if (!socket.connected) socket.connect();

async function scan() {
  scanningStore.set(true);
  scanningPlatforms.value = [];

  if (!socket.connected) socket.connect();

  socket.emit("scan", {
    platforms: platformsToScan.value.map((p) => p.id),
    type: scanType.value,
    apis: metadataSources.value.map((s) => s.value),
  });
}

socket.on("scan:done", (stats) => {
  scanStats.value = stats;
});

async function stopScan() {
  socket.emit("scan:stop");
}
</script>

<template>
  <!-- Platform selector -->
  <v-row class="px-4 pt-4 align-center" no-gutters>
    <v-col cols="6" class="pr-1">
      <v-select
        label="Platforms"
        item-title="name"
        v-model="platformsToScan"
        :items="platforms.value"
        variant="outlined"
        density="comfortable"
        rounded="0"
        multiple
        return-object
        clearable
        hide-details
        chips
      >
        <template v-slot:item="{ props, item }">
          <v-list-item class="py-2" v-bind="props" :title="item.raw.name ?? ''">
            <template v-slot:prepend>
              <v-avatar :rounded="0" size="35">
                <platform-icon :key="item.raw.slug" :slug="item.raw.slug" />
              </v-avatar>
            </template>
          </v-list-item>
        </template>
      </v-select>
    </v-col>
    <v-col cols="3" class="pr-1">
      <v-select
        label="Metadata sources"
        item-title="name"
        v-model="metadataSources"
        :items="metadataOptions"
        variant="outlined"
        density="comfortable"
        multiple
        return-object
        clearable
        hide-details
        rounded="0"
        chips
      >
        <template v-slot:item="{ props, item }">
          <v-list-item
            v-bind="props"
            :title="item.raw.name"
            :subtitle="item.raw.disabled ? 'API key missing or invalid' : ''"
            :disabled="item.raw.disabled"
            :prepend-icon="
              metadataSources.map((s) => s.value).includes(item.raw.value)
                ? 'mdi-checkbox-marked'
                : 'mdi-square-outline'
            "
          ></v-list-item>
        </template>
      </v-select>
    </v-col>
    <v-col cols="3">
      <!-- Scan options -->
      <v-select
        hide-details
        density="comfortable"
        variant="outlined"
        label="Scan option"
        v-model="scanType"
        :items="scanOptions"
        class="py-3"
      >
        <template v-slot:item="{ props, item }">
          <v-list-item
            v-bind="props"
            :subtitle="item.raw.subtitle"
          ></v-list-item>
        </template>
      </v-select>
    </v-col>
  </v-row>

  <v-row class="pa-4 align-center" no-gutters>
    <v-btn
      @click="scan()"
      :disabled="scanning || metadataSources.length == 0"
      prepend-icon="mdi-magnify-scan"
      rounded="4"
      height="40"
      :color="scanning || metadataSources.length == 0 ? '' : 'romm-accent-1'"
      :loading="scanning"
    >
      Scan
      <template v-slot:loader>
        <v-progress-circular
          color="romm-accent-1"
          :width="2"
          :size="20"
          indeterminate
        />
      </template>
    </v-btn>
    <v-btn
      class="ml-2"
      @click="stopScan()"
      :disabled="!scanning"
      prepend-icon="mdi-alert-octagon"
      rounded="4"
      height="40"
      :color="scanning ? 'red' : ''"
    >
      Abort
    </v-btn>
    <span
      v-if="metadataSources.length == 0"
      class="ml-4 text-caption text-yellow"
    >
      <v-icon class="mr-2">mdi-alert</v-icon>
      Please select at least one metadata source.
    </span>
  </v-row>

  <v-divider
    class="border-opacity-100 mx-4"
    color="romm-accent-1"
    :thickness="1"
  />

  <!-- Scan log -->
  <div class="overflow-y-auto scan-log mt-4">
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
          <span v-if="rom.igdb_id" class="ml-10">
            • Identified <b>{{ rom.name }} 👾</b>
          </span>
          <span v-else class="ml-10">
            • {{ rom.file_name }} not found in IGDB ❌
          </span>
        </v-list-item>
      </v-col>
    </v-row>
  </div>

  <!-- Scan stats -->
  <v-row class="pa-4 align-center" no-gutters v-if="!scanning">
    <v-col>
      <v-chip
        v-if="scanningPlatforms.length > 0"
        color="romm-accent-1"
        text-color="white"
        class="mr-2"
      >
        <v-icon left>mdi-information</v-icon>&nbsp; Platforms:
        {{ scanStats.scanned_platforms }} scanned, with
        {{ scanStats.added_platforms }} new and
        {{ scanStats.metadata_platforms }} identified
      </v-chip>
      <v-chip
        v-if="scanningPlatforms.length > 0"
        color="romm-accent-1"
        text-color="white"
        class="mr-2"
      >
        <v-icon left>mdi-information</v-icon>&nbsp; Roms:
        {{ scanStats.scanned_roms }} scanned, with
        {{ scanStats.added_roms }} new and
        {{ scanStats.metadata_roms }} identified
      </v-chip>
    </v-col>
  </v-row>
</template>

<style scoped>
.scan-log {
  max-height: calc(100vh - 245px);
}
</style>
