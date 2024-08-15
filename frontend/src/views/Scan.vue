<script setup lang="ts">
import RAvatar from "@/components/common/Game/RAvatar.vue";
import PlatformIcon from "@/components/common/Platform/Icon.vue";
import socket from "@/services/socket";
import storeHeartbeat from "@/stores/heartbeat";
import storePlatforms, { type Platform } from "@/stores/platforms";
import storeScanning from "@/stores/scanning";
import { storeToRefs } from "pinia";
import { computed, ref, watch } from "vue";
import { useDisplay } from "vuetify";

// Props
const { xs, smAndDown } = useDisplay();
const scanningStore = storeScanning();
const { scanning, scanningPlatforms, scanStats } = storeToRefs(scanningStore);
const platforms = storePlatforms();
const heartbeat = storeHeartbeat();
const platformsToScan = ref<Platform[]>([]);
const panels = ref([0]);
const panelIndex = ref(0);
// Use a computed property to reactively update metadataOptions based on heartbeat
const metadataOptions = computed(() => [
  {
    name: "IGDB",
    value: "igdb",
    logo_path: "/assets/scrappers/igdb.png",
    disabled: !heartbeat.value.METADATA_SOURCES?.IGDB_API_ENABLED,
  },
  {
    name: "MobyGames",
    value: "moby",
    logo_path: "/assets/scrappers/moby.png",
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

// Adding each new scanned platform to panelIndex to be open by default
watch(scanningPlatforms, () => {
  panelIndex.value += 1;
  panels.value.push(panelIndex.value);
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

// TODO: fix abort scan
async function stopScan() {
  socket.emit("scan:stop");
}
</script>

<template>
  <v-row class="align-center pt-4 px-4" no-gutters>
    <!-- Platform selector -->
    <v-col cols="12" md="5" lg="6" class="px-1">
      <v-select
        :menu-props="{ maxHeight: 650 }"
        prepend-inner-icon="mdi-controller"
        v-model="platformsToScan"
        label="Platforms"
        item-title="name"
        :items="platforms.all"
        variant="outlined"
        density="comfortable"
        multiple
        return-object
        clearable
        hide-details
        chips
      >
        <template #item="{ props, item }">
          <v-list-item
            class="py-4"
            v-bind="props"
            :title="item.raw.name ?? ''"
            :subtitle="item.raw.fs_slug"
          >
            <template #prepend>
              <platform-icon
                :key="item.raw.slug"
                :size="35"
                :slug="item.raw.slug"
                :name="item.raw.name"
              />
            </template>
            <template #append>
              <v-chip class="ml-2" size="x-small" label>
                {{ item.raw.rom_count }}
              </v-chip>
            </template>
          </v-list-item>
        </template>
        <template #chip="{ item }">
          <v-chip>
            <platform-icon
              :key="item.raw.slug"
              :slug="item.raw.slug"
              :name="item.raw.name"
              :size="20"
              class="mr-2"
            />
            {{ item.raw.name }}
          </v-chip>
        </template>
      </v-select>
    </v-col>

    <!-- Source options -->
    <v-col class="px-1" cols="12" md="5" lg="4" :class="{ 'mt-3': smAndDown }">
      <v-select
        prepend-inner-icon="mdi-database-search"
        v-model="metadataSources"
        label="Metadata sources"
        item-title="name"
        :items="metadataOptions"
        variant="outlined"
        density="comfortable"
        multiple
        return-object
        clearable
        hide-details
        chips
      >
        <template #item="{ props, item }">
          <v-list-item
            v-bind="props"
            :title="item.raw.name"
            :subtitle="item.raw.disabled ? 'API key missing or invalid' : ''"
            :disabled="item.raw.disabled"
          >
            <template #prepend>
              <v-avatar size="25" rounded="1">
                <v-img :src="item.raw.logo_path" />
              </v-avatar>
            </template>
          </v-list-item>
        </template>
        <template #chip="{ item }">
          <v-chip>
            <v-avatar class="mr-2" size="15" rounded="1">
              <v-img
                :src="`/assets/scrappers/${item.raw.name
                  .slice(0, 4)
                  .toLowerCase()}.png`"
              />
            </v-avatar>
            {{ item.raw.name }}
          </v-chip>
        </template>
      </v-select>
    </v-col>
    <!-- Scan options -->
    <v-col class="px-1" cols="12" md="2" :class="{ 'mt-3': smAndDown }">
      <v-select
        prepend-inner-icon="mdi-magnify-scan"
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
  <v-row
    class="px-4 mt-3 align-center"
    :class="{ 'justify-center': smAndDown }"
    no-gutters
  >
    <v-btn
      :disabled="scanning || metadataSources.length == 0"
      rounded="4"
      height="40"
      :loading="scanning"
      @click="scan()"
    >
      <template #prepend>
        <v-icon
          :color="
            scanning || metadataSources.length == 0 ? '' : 'romm-accent-1'
          "
          >mdi-magnify-scan</v-icon
        >
      </template>
      <span
        :class="{
          'text-romm-accent-1': !(scanning || metadataSources.length == 0),
        }"
        >Scan</span
      >
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
      <span :class="{ 'text-romm-red': scanning }">Abort</span>
    </v-btn>
    <v-btn
      prepend-icon="mdi-table-cog"
      rounded="4"
      height="40"
      class="ml-2"
      :to="{ name: 'management' }"
    >
      Manage
    </v-btn>
  </v-row>
  <v-row
    v-if="metadataSources.length == 0"
    no-gutters
    class="mt-3 justify-center"
  >
    <v-list-item class="text-caption text-yellow py-0">
      <v-icon>mdi-alert</v-icon
      ><span class="ml-2">Please select at least one metadata source.</span>
    </v-list-item>
  </v-row>

  <v-divider
    class="border-opacity-100 mt-3"
    :class="{ 'mx-4': !smAndDown }"
    color="romm-accent-1"
  />

  <!-- Scan log -->
  <v-card
    elevation="0"
    rounded="0"
    class="bg-secondary mx-auto mb-1"
    max-width="800"
  >
    <v-card-text class="pa-0">
      <v-expansion-panels
        :model-value="panels"
        multiple
        flat
        rounded="0"
        variant="accordion"
      >
        <v-expansion-panel
          v-for="platform in scanningPlatforms"
          :key="platform.id"
        >
          <v-expansion-panel-title>
            <v-list-item class="pa-0">
              <template #prepend>
                <v-avatar :rounded="0" size="40">
                  <platform-icon :key="platform.slug" :slug="platform.slug" :name="platform.name" />
                </v-avatar>
              </template>
              {{ platform.name }}
              <template #append>
                <v-chip
                  class="ml-3"
                  color="romm-accent-1"
                  size="x-small"
                  label
                  >{{ platform.roms.length }}</v-chip
                >
              </template>
            </v-list-item>
          </v-expansion-panel-title>
          <v-expansion-panel-text class="bg-terciary">
            <v-list-item
              v-for="rom in platform.roms"
              :key="rom.id"
              class="text-body-2 romm-grey px-10 py-2"
              :to="{ name: 'rom', params: { rom: rom.id } }"
            >
              <template #prepend>
                <r-avatar :rom="rom" />
              </template>
              <v-row no-gutters>
                <span
                  :class="{ 'text-romm-red': !rom.igdb_id && !rom.moby_id }"
                  >{{ rom.name }}</span
                >
                <span v-if="!rom.igdb_id && !rom.moby_id" class="ml-1">❌</span>
              </v-row>
              <v-row no-gutters>
                <v-col class="text-romm-accent-1">
                  {{ rom.file_name }}
                </v-col>
              </v-row>
            </v-list-item>
            <v-list-item
              v-if="platform.roms.length == 0"
              class="text-center mt-2"
            >
              No new/changed roms found
            </v-list-item>
          </v-expansion-panel-text>
        </v-expansion-panel>
      </v-expansion-panels>
    </v-card-text>
  </v-card>

  <!-- Scan stats -->
  <v-bottom-navigation
    :active="scanningPlatforms.length > 0"
    :elevation="0"
    height="40"
    class="text-caption align-center"
    ><v-chip variant="outlined" color="terciary" class="px-1">
      <v-icon class="text-white"> mdi-information </v-icon>
      <v-chip
        v-if="scanningPlatforms.length > 0"
        color="romm-accent-1"
        text-color="white"
        size="small"
        class="ml-1 my-1"
      >
        <v-icon left>mdi-controller</v-icon>
        <span>&nbsp;Platforms: {{ scanningPlatforms.length }} scanned</span>
        <span v-if="!xs">, with {{ scanStats.added_platforms }} new</span>
        <span v-if="!xs"
          >&nbsp;and {{ scanStats.metadata_platforms }} identified</span
        >
      </v-chip>
      <v-chip
        v-if="scanningPlatforms.length > 0"
        color="romm-accent-1"
        size="small"
        text-color="white"
        class="ml-1 my-1"
      >
        <v-icon left> mdi-disc </v-icon>
        <span>&nbsp; Roms: {{ scanStats.scanned_roms }} scanned</span>
        <span v-if="!xs">, with {{ scanStats.added_roms }} new</span>
        <span v-if="!xs"
          >&nbsp;and {{ scanStats.metadata_roms }} identified</span
        >
      </v-chip>
    </v-chip>
  </v-bottom-navigation>
</template>
