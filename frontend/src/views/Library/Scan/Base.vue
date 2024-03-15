<script setup lang="ts">
import PlatformIcon from "@/components/Platform/PlatformIcon.vue";
import socket from "@/services/socket";
import storePlatforms, { type Platform } from "@/stores/platforms";
import storeScanning from "@/stores/scanning";
import storeHeartbeat from "@/stores/heartbeat";
import { storeToRefs } from "pinia";
import { ref } from "vue";

// Props
const scanningStore = storeScanning();
const { scanning, scanningPlatforms } = storeToRefs(scanningStore);
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

async function stopScan() {
  socket.emit("scan:stop");
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

  <v-row class="px-4 pt-2" no-gutters>
    <!-- Scan options -->
    <v-col cols="3" class="pt-1 px-4">
      <v-select
        label="Metadata sources"
        item-title="name"
        v-model="metadataSources"
        :items="metadataOptions"
        variant="outlined"
        density="compact"
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
    <v-col cols="4" class="text-truncate">
      <v-select
        density="compact"
        class="my-1"
        variant="outlined"
        label="Scan option"
        v-model="scanType"
        :items="scanOptions"
      >
        <template v-slot:item="{ props, item }">
          <v-list-item
            v-bind="props"
            :subtitle="item.raw.subtitle"
          ></v-list-item>
        </template>
      </v-select>
    </v-col>
    <v-col cols="1" class="pt-1 px-4">
      <v-btn
        @click="scan()"
        :disabled="scanning"
        prepend-icon="mdi-magnify-scan"
        rounded="4"
        height="40"
        color="romm-accent-1"
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
    </v-col>
    <v-col cols="1" class="pt-1 px-4">
      <v-btn
        @click="stopScan()"
        :disabled="!scanning"
        prepend-icon="mdi-alert-octagon"
        rounded="4"
        height="40"
        color="red"
      >
        Stop
      </v-btn>
    </v-col>
  </v-row>

  <v-divider
    class="border-opacity-100 mx-4"
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
        <span v-else class="ml-10"> • {{ rom.file_name }} not found ❌ </span>
      </v-list-item>
    </v-col>
  </v-row>
</template>
