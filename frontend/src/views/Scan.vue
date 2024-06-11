<script setup lang="ts">
import PlatformIcon from "@/components/Platform/Icon.vue";
import socket from "@/services/socket";
import storeHeartbeat from "@/stores/heartbeat";
import storePlatforms, { type Platform } from "@/stores/platforms";
import storeScanning from "@/stores/scanning";
import { storeToRefs } from "pinia";
import { computed, ref, watch } from "vue";
import { useDisplay } from "vuetify";

// Props
const scanningStore = storeScanning();
const { scanning, scanningPlatforms, scanStats } = storeToRefs(scanningStore);
const platforms = storePlatforms();
const heartbeat = storeHeartbeat();
const { smAndDown } = useDisplay();

const platformsToScan = ref<Platform[]>([]);

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
// Since metadataOptions is now a computed property, it will automatically update.
// Therefore, we only need to watch metadataOptions for changes.
watch(metadataOptions, (newOptions) => {
  metadataSources.value = newOptions.filter((option) => !option.disabled);
});

const scanOptions = [
  {
    title: "New platforms",
    subtitle: "Scan new platforms only (fastest)",
    value: "new_platforms",
  },
  { title: "Quick scan", subtitle: "Scan new files only", value: "quick" },
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
const scanType = ref("quick");

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
  <v-row class="align-center pt-4 px-4" no-gutters>
    <!-- Platform selector -->
    <v-col cols="12" md="6">
      <v-autocomplete
        v-model="platformsToScan"
        label="Platforms"
        item-title="name"
        :items="platforms.value"
        variant="outlined"
        density="comfortable"
        multiple
        return-object
        clearable
        hide-details
        chips
      >
        <template #item="{ props, item }">
          <v-list-item class="py-2" v-bind="props" :title="item.raw.name ?? ''">
            <template #prepend>
              <platform-icon
                :key="item.raw.slug"
                :size="35"
                :slug="item.raw.slug"
              />
            </template>
          </v-list-item>
        </template>
      </v-autocomplete>
    </v-col>

    <!-- Source options -->
    <v-col cols="12" sm="5" md="3" :class="{ 'mt-3': smAndDown }">
      <v-autocomplete
        v-model="metadataSources"
        label="Metadata sources"
        item-title="name"
        :items="metadataOptions"
        variant="outlined"
        density="comfortable"
        multiple
        chips
        class="px-2"
        return-object
        clearable
        hide-details
      >
        <template #item="{ props, item }">
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
          />
        </template>
      </v-autocomplete>
    </v-col>
    <!-- Scan options -->
    <v-col cols="12" sm="7" md="3" class="pr-1" :class="{ 'mt-3': smAndDown }">
      <v-select
        v-model="scanType"
        hide-details
        density="comfortable"
        variant="outlined"
        label="Scan option"
        :items="scanOptions"
      >
        <template #item="{ props, item }">
          <v-list-item v-bind="props" :subtitle="item.raw.subtitle" />
        </template>
      </v-select>
    </v-col>
  </v-row>

  <!-- Scan buttons -->
  <v-row class="pa-4 align-center" no-gutters>
    <v-btn
      :disabled="scanning || metadataSources.length == 0"
      rounded="4"
      height="40"
      :loading="scanning"
      @click="scan()"
    >
      <template #prepend>
        <v-icon color="romm-accent-1">mdi-magnify-scan</v-icon>
      </template>
      <span class="text-romm-accent-1">Scan</span>
      <template #loader>
        <v-progress-circular
          color="romm-accent-1"
          :width="2"
          :size="20"
          indeterminate
        />
      </template>
    </v-btn>
    <v-btn
      :disabled="!scanning"
      class="ml-2"
      rounded="4"
      height="40"
      @click="stopScan()"
    >
      <template #prepend>
        <v-icon :color="scanning ? 'red' : ''">mdi-alert-octagon</v-icon>
      </template>
      <span :class="{ 'text-red': scanning }">Abort</span>
    </v-btn>
    <span
      v-if="metadataSources.length == 0"
      class="ml-4 text-caption text-yellow py-0 "
    >
      <v-icon class="mr-2">mdi-alert</v-icon>
      Please select at least one metadata source.
    </span>
  </v-row>

  <v-divider class="border-opacity-100 mx-4" color="romm-accent-1" />

  <!-- Scan log -->
  <div class="overflow-y-auto scan-log mt-4">
    <v-row
      v-for="platform in scanningPlatforms"
      :key="platform.id"
      no-gutters
      class="align-center pa-4"
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
          :key="rom.id"
          class="text-body-2 romm-grey"
          :to="{ name: 'rom', params: { rom: rom.id } }"
        >
          <span v-if="rom.igdb_id || rom.moby_id" class="ml-10">
            • Identified <b>{{ rom.name }} 👾</b>
          </span>
          <span v-else class="ml-10">
            • {{ rom.file_name }} not found in metadata sources ❌
          </span>
        </v-list-item>
      </v-col>
    </v-row>
  </div>

  <!-- Scan stats -->
  <v-bottom-navigation :elevation="0" height="40" class="text-caption">
    <v-chip
      v-if="scanningPlatforms.length > 0"
      color="romm-accent-1"
      text-color="white"
      class="mr-2 my-1"
    >
      <v-icon left> mdi-information </v-icon>&nbsp; Platforms:
      {{ scanningPlatforms.length }} scanned, with
      {{ scanStats.added_platforms }} new and
      {{ scanStats.metadata_platforms }} identified
    </v-chip>
    <v-chip
      v-if="scanningPlatforms.length > 0"
      color="romm-accent-1"
      text-color="white"
      class="my-1"
    >
      <v-icon left> mdi-information </v-icon>&nbsp; Roms:
      {{ scanStats.scanned_roms }} scanned, with {{ scanStats.added_roms }} new
      and {{ scanStats.metadata_roms }} identified
    </v-chip>
  </v-bottom-navigation>
</template>

<style scoped>
.scan-log {
  max-height: calc(100vh - 200px);
}
</style>
