<script setup lang="ts">
import RAvatarRom from "@/components/common/Game/RAvatar.vue";
import RomListItem from "@/components/common/Game/ListItem.vue";
import PlatformIcon from "@/components/common/Platform/Icon.vue";
import socket from "@/services/socket";
import storeHeartbeat from "@/stores/heartbeat";
import storePlatforms, { type Platform } from "@/stores/platforms";
import storeScanning from "@/stores/scanning";
import { storeToRefs } from "pinia";
import { computed, ref, watch } from "vue";
import { useDisplay } from "vuetify";
import { useI18n } from "vue-i18n";

// Props
const { t } = useI18n();
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
    title: t("scan.new-platforms"),
    subtitle: t("scan.new-platforms-desc"),
    value: "new_platforms",
  },
  {
    title: t("scan.quick-scan"),
    subtitle: t("scan.quick-scan-desc"),
    value: "quick",
  },
  {
    title: t("scan.unidentified-games"),
    subtitle: t("scan.unidentified-games-desc"),
    value: "unidentified",
  },
  {
    title: t("scan.partial-metadata"),
    subtitle: t("scan.partial-metadata-desc"),
    value: "partial",
  },
  {
    title: t("scan.complete-rescan"),
    subtitle: t("scan.complete-rescan-desc"),
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
      <!-- TODO: add 'ALL' default option -->
      <v-select
        v-model="platformsToScan"
        :items="platforms.allPlatforms"
        :menu-props="{ maxHeight: 650 }"
        :label="t('common.platforms')"
        item-title="name"
        prepend-inner-icon="mdi-controller"
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
            class="py-4"
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
    <v-col cols="12" md="5" lg="4" class="px-1" :class="{ 'mt-3': smAndDown }">
      <v-select
        v-model="metadataSources"
        :items="metadataOptions"
        :label="t('scan.metadata-sources')"
        item-title="name"
        prepend-inner-icon="mdi-database-search"
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
            :subtitle="item.raw.disabled ? t('scan.api-key-missing') : ''"
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
    <v-col cols="12" md="2" class="px-1" :class="{ 'mt-3': smAndDown }">
      <v-select
        v-model="scanType"
        :items="scanOptions"
        :label="t('scan.scan-options')"
        prepend-inner-icon="mdi-magnify-scan"
        hide-details
        density="comfortable"
        variant="outlined"
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
      :disabled="scanning"
      :loading="scanning"
      rounded="4"
      height="40"
      @click="scan()"
    >
      <template #prepend>
        <v-icon :color="scanning ? '' : 'romm-accent-1'"
          >mdi-magnify-scan</v-icon
        >
      </template>
      {{ t("scan.scan") }}
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
      {{ t("scan.abort") }}
    </v-btn>
    <v-btn
      prepend-icon="mdi-table-cog"
      rounded="4"
      height="40"
      class="ml-2"
      :to="{ name: 'libraryManagement' }"
    >
      {{ t("scan.manage-library") }}
    </v-btn>
  </v-row>

  <v-row
    v-if="metadataSources.length == 0"
    no-gutters
    class="mt-3 justify-center"
  >
    <v-list-item class="text-caption text-yellow py-0">
      <v-icon>mdi-alert</v-icon
      ><span class="ml-2">{{ t("scan.select-one-source") }}</span>
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
        v-model="panels"
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
                  <platform-icon
                    :key="platform.slug"
                    :slug="platform.slug"
                    :name="platform.name"
                  />
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
            <rom-list-item
              v-for="rom in platform.roms"
              class="pa-4"
              :rom="rom"
              with-link
              with-filename
            >
              <template #append-body>
                <v-chip
                  v-if="!rom.igdb_id && !rom.moby_id"
                  color="red"
                  size="x-small"
                  label
                  >Not identified<v-icon class="ml-1">mdi-close</v-icon></v-chip
                >
              </template>
            </rom-list-item>
            <v-list-item
              v-if="platform.roms.length == 0"
              class="text-center my-2"
            >
              {{ t("scan.no-new-roms") }}
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
  >
    <v-chip variant="outlined" color="terciary" class="px-1">
      <v-icon class="text-white"> mdi-information </v-icon>
      <v-chip
        v-if="scanningPlatforms.length > 0"
        color="romm-accent-1"
        text-color="white"
        size="small"
        class="ml-1 my-1"
      >
        <v-icon left>mdi-controller</v-icon>
        <span v-if="xs" class="ml-2">{{
          t("scan.platforms-scanned-n", scanningPlatforms.length)
        }}</span>
        <span class="ml-2" v-else>{{
          t("scan.platforms-scanned-with-details", {
            n_platforms: scanningPlatforms.length,
            n_added_platforms: scanStats.added_platforms,
            n_identified_platforms: scanStats.metadata_platforms,
          })
        }}</span>
      </v-chip>
      <v-chip
        v-if="scanningPlatforms.length > 0"
        color="romm-accent-1"
        size="small"
        text-color="white"
        class="ml-1 my-1"
      >
        <v-icon left> mdi-disc </v-icon>
        <span v-if="xs" class="ml-2">{{
          t("scan.roms-scanned-n", scanStats.scanned_roms)
        }}</span>
        <span class="ml-2" v-else>{{
          t("scan.roms-scanned-with-details", {
            n_roms: scanStats.scanned_roms,
            n_added_roms: scanStats.added_roms,
            n_identified_roms: scanStats.metadata_roms,
          })
        }}</span>
      </v-chip>
    </v-chip>
  </v-bottom-navigation>
</template>
<style lang="css">
.v-expansion-panel-text__wrapper {
  padding: 0px;
}
</style>
