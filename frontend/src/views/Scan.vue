<script setup lang="ts">
import { useLocalStorage } from "@vueuse/core";
import { storeToRefs } from "pinia";
import { computed, ref, useTemplateRef, watch } from "vue";
import { useI18n } from "vue-i18n";
import { useDisplay } from "vuetify";
import ScanPlatform from "@/components/Scan/ScanPlatform.vue";
import MissingFromFSIcon from "@/components/common/MissingFromFSIcon.vue";
import PlatformIcon from "@/components/common/Platform/PlatformIcon.vue";
import { useAutoScroll } from "@/composables/useAutoScroll";
import { ROUTES } from "@/plugins/router";
import socket from "@/services/socket";
import storeHeartbeat, { type MetadataOption } from "@/stores/heartbeat";
import storePlatforms from "@/stores/platforms";
import storeScanning from "@/stores/scanning";

const LOCAL_STORAGE_METADATA_SOURCES_KEY = "scan.metadataSources";
const LOCAL_STORAGE_CALCULATE_HASHES_KEY = "scan.calculateHashes";

const { t } = useI18n();
const { xs, smAndDown } = useDisplay();
const scanningStore = storeScanning();
const { scanning, scanningPlatforms, scanStats } = storeToRefs(scanningStore);
const platformsStore = storePlatforms();
const { filteredPlatforms } = storeToRefs(platformsStore);
const heartbeat = storeHeartbeat();
const platformsToScan = ref<number[]>([]);
const panels = ref<number[]>([]);
const scanLog = useTemplateRef<HTMLDivElement>("scan-log-ref");
const expansionPanels = useTemplateRef<HTMLDivElement>("expansion-panels-ref");

useAutoScroll(scanLog, expansionPanels);

const sortedPlatforms = computed(() => {
  return filteredPlatforms.value.sort((a, b) =>
    a.display_name.localeCompare(b.display_name),
  );
});
const calculateHashes = useLocalStorage(
  LOCAL_STORAGE_CALCULATE_HASHES_KEY,
  true,
);
const metadataOptions = computed(() => {
  return heartbeat.getMetadataOptionsByPriority().map((option) => ({
    ...option,
    disabled:
      option.disabled ||
      (!calculateHashes.value &&
        (option.value === "hasheous" || option.value === "ra"))
        ? option.value === "hasheous"
          ? t("scan.hasheous-requires-hashes")
          : option.value === "ra"
            ? t("scan.retroachievements-requires-hashes")
            : option.disabled
        : option.disabled,
  }));
});
const storedMetadataSources = useLocalStorage(
  LOCAL_STORAGE_METADATA_SOURCES_KEY,
  [] as string[],
);
const metadataSources = ref<MetadataOption[]>(
  metadataOptions.value.filter(
    (m) => storedMetadataSources.value.includes(m.value) && !m.disabled,
  ) || heartbeat.getEnabledMetadataOptions(),
);

// Watch for changes in calculateHashes to remove hash-dependent sources
watch(calculateHashes, (newValue) => {
  if (!newValue) {
    // Remove Hasheous and RetroAchievements when hashes are disabled
    metadataSources.value = metadataSources.value.filter(
      (source) => source.value !== "hasheous" && source.value !== "ra",
    );
  }
});

watch(metadataOptions, (newOptions) => {
  // Remove any sources that are now disabled
  metadataSources.value = metadataSources.value.filter((s) =>
    newOptions.some((opt) => opt.value === s.value && !opt.disabled),
  );
});

// Adding each new scanned platform to panelIndex to be open by default
watch(
  scanningPlatforms,
  () => {
    panels.value = scanningPlatforms.value
      .map((p, index) => (p.roms.length > 0 ? index : -1))
      .filter((index) => index !== -1);
  },
  { deep: true },
);

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
    title: t("scan.unmatched-games"),
    subtitle: t("scan.unmatched-games-desc"),
    value: "unmatched",
  },
  {
    title: t("scan.update-metadata"),
    subtitle: t("scan.update-metadata-desc"),
    value: "update",
  },
  {
    title: t("scan.hashes"),
    subtitle: t("scan.hashes-desc"),
    value: "hashes",
  },
  {
    title: t("scan.complete-rescan"),
    subtitle: t("scan.complete-rescan-desc"),
    value: "complete",
  },
];
const scanType = ref("quick");

async function scan() {
  scanningStore.setScanning(true);
  scanningPlatforms.value = [];

  if (!socket.connected) socket.connect();

  // Store selected meta sources in storage
  storedMetadataSources.value = metadataSources.value.map((s) => s.value);

  socket.emit("scan", {
    platforms: platformsToScan.value,
    type: scanType.value,
    apis: metadataSources.value.map((s) => s.value),
    calculate_hashes: calculateHashes.value,
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
  <div class="d-flex flex-column h-screen">
    <div>
      <v-row class="align-center pt-4 px-4" no-gutters>
        <!-- Platform selector -->
        <v-col cols="12" md="5" lg="6" class="px-1">
          <v-select
            v-model="platformsToScan"
            :items="sortedPlatforms"
            :menu-props="{ maxHeight: 650 }"
            :label="t('common.platforms')"
            item-title="name"
            item-value="id"
            prepend-inner-icon="mdi-controller"
            variant="outlined"
            density="comfortable"
            multiple
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
                  <PlatformIcon
                    :key="item.raw.slug"
                    :size="35"
                    :slug="item.raw.slug"
                    :name="item.raw.name"
                    :fs-slug="item.raw.fs_slug"
                  />
                </template>
                <template #append>
                  <MissingFromFSIcon
                    v-if="item.raw.missing_from_fs"
                    text="Missing platform from filesystem"
                    chip
                    chip-label
                    chip-density="compact"
                    class="ml-2"
                  />
                  <v-row
                    v-if="item.raw.is_identified"
                    class="text-white text-shadow text-center"
                    no-gutters
                  >
                    <v-col cols="12">
                      <v-avatar
                        v-if="item.raw.igdb_id"
                        variant="text"
                        size="25"
                        rounded
                        class="mr-1"
                      >
                        <v-img src="/assets/scrappers/igdb.png" />
                      </v-avatar>

                      <v-avatar
                        v-if="item.raw.ss_id"
                        variant="text"
                        size="25"
                        rounded
                        class="mr-1"
                      >
                        <v-img src="/assets/scrappers/ss.png" />
                      </v-avatar>

                      <v-avatar
                        v-if="item.raw.moby_slug"
                        variant="text"
                        size="25"
                        rounded
                        class="mr-1"
                      >
                        <v-img src="/assets/scrappers/moby.png" />
                      </v-avatar>

                      <v-avatar
                        v-if="item.raw.ra_id"
                        variant="text"
                        size="25"
                        rounded
                        class="mr-1"
                      >
                        <v-img src="/assets/scrappers/ra.png" />
                      </v-avatar>

                      <v-avatar
                        v-if="item.raw.launchbox_id"
                        variant="text"
                        size="25"
                        rounded
                        class="mr-1"
                        style="background: #185a7c"
                      >
                        <v-img src="/assets/scrappers/launchbox.png" />
                      </v-avatar>

                      <v-avatar
                        v-if="item.raw.hasheous_id"
                        variant="text"
                        size="25"
                        rounded
                        class="mr-1"
                      >
                        <v-img src="/assets/scrappers/hasheous.png" />
                      </v-avatar>

                      <v-avatar
                        v-if="item.raw.flashpoint_id"
                        variant="text"
                        size="25"
                        rounded
                        class="mr-1"
                      >
                        <v-img src="/assets/scrappers/flashpoint.png" />
                      </v-avatar>

                      <v-avatar
                        v-if="item.raw.hltb_slug"
                        class="bg-surface"
                        variant="text"
                        size="25"
                        rounded
                      >
                        <v-img src="/assets/scrappers/hltb.png" />
                      </v-avatar>
                    </v-col>
                  </v-row>
                  <v-row
                    v-else
                    class="text-white text-shadow text-center"
                    no-gutters
                  >
                    <v-chip color="red" size="small" label>
                      <v-icon class="mr-1"> mdi-close </v-icon>
                      {{ t("scan.not-identified").toUpperCase() }}
                    </v-chip>
                  </v-row>
                  <v-chip class="ml-1" size="small" label>
                    {{ item.raw.rom_count }}
                  </v-chip>
                </template>
              </v-list-item>
            </template>
            <template #chip="{ item }">
              <v-chip>
                <PlatformIcon
                  :key="item.raw.slug"
                  :slug="item.raw.slug"
                  :name="item.raw.name"
                  :fs-slug="item.raw.fs_slug"
                  :size="20"
                />
                <div class="ml-1">
                  {{ item.raw.name }}
                </div>
              </v-chip>
            </template>
          </v-select>
        </v-col>

        <!-- Source options -->
        <v-col
          cols="12"
          md="5"
          lg="4"
          class="px-1"
          :class="{ 'mt-3': smAndDown }"
        >
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
                :subtitle="item.raw.disabled"
                :disabled="Boolean(item.raw.disabled)"
              >
                <template #prepend>
                  <v-avatar size="25" rounded="1">
                    <v-img :src="item.raw.logo_path" />
                  </v-avatar>
                </template>
              </v-list-item>
            </template>
            <template #chip="{ item }">
              <v-avatar class="mx-1" size="24" rounded="1">
                <v-img :src="item.raw.logo_path" />
              </v-avatar>
            </template>
          </v-select>
        </v-col>

        <!-- Scan options -->
        <v-col
          cols="12"
          md="2"
          class="px-1 d-flex align-center"
          :class="{ 'mt-3': smAndDown }"
        >
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
            <template #append-inner>
              <a
                href="https://docs.romm.app/latest/Usage/LibraryManagement/#scan"
                target="_blank"
              >
                <v-icon
                  @click.stop
                  icon="mdi-information-outline"
                  size="small"
                  class="ml-2"
                  title="See documentation"
                />
              </a>
            </template>
          </v-select>
        </v-col>
      </v-row>

      <!-- Scan buttons -->
      <v-row
        class="px-4 mt-1 ml-1 align-center"
        :class="{ 'justify-center': smAndDown }"
        no-gutters
      >
        <div class="d-flex align-center">
          <v-btn
            height="40"
            class="ma-1"
            @click="calculateHashes = !calculateHashes"
          >
            <template #prepend>
              <v-icon
                size="x-large"
                :color="calculateHashes ? 'primary' : ''"
                :icon="
                  calculateHashes
                    ? 'mdi-toggle-switch'
                    : 'mdi-toggle-switch-off'
                "
              />
            </template>
            <template #append>
              <v-menu open-on-hover location="bottom start">
                <template #activator="{ props }">
                  <v-icon
                    v-bind="props"
                    icon="mdi-information-outline"
                    size="small"
                    class="ml-2"
                  />
                </template>
                <v-card max-width="400">
                  <v-card-text>
                    <div
                      v-html="
                        calculateHashes
                          ? t('scan.hashes-enabled-tooltip')
                          : t('scan.hashes-disabled-tooltip')
                      "
                    ></div>
                  </v-card-text>
                </v-card>
              </v-menu>
            </template>
            {{ t("scan.calculate-hashes") }}
          </v-btn>
        </div>
        <v-btn
          :disabled="scanning"
          :loading="scanning"
          rounded="4"
          height="40"
          @click="scan"
          class="ma-1"
        >
          <template #prepend>
            <v-icon :color="scanning ? '' : 'primary'">
              mdi-magnify-scan
            </v-icon>
          </template>
          {{ t("scan.scan") }}
          <template #loader>
            <v-progress-circular
              color="primary"
              :width="2"
              :size="20"
              indeterminate
            />
          </template>
        </v-btn>
        <v-btn
          :disabled="!scanning"
          class="ma-1"
          rounded="4"
          height="40"
          @click="stopScan"
        >
          <template #prepend>
            <v-icon :color="scanning ? 'red' : ''"> mdi-alert-octagon </v-icon>
          </template>
          {{ t("scan.abort") }}
        </v-btn>
        <v-btn
          prepend-icon="mdi-table-cog"
          rounded="4"
          height="40"
          class="ma-1"
          :to="{ name: ROUTES.LIBRARY_MANAGEMENT }"
        >
          {{ t("scan.manage-library") }}
        </v-btn>
        <v-alert
          v-if="metadataSources.length == 0"
          type="warning"
          icon="mdi-alert"
          variant="tonal"
          class="my-1 mx-4"
          density="compact"
        >
          <span>{{ t("scan.select-one-source") }}</span>
        </v-alert>
      </v-row>
      <v-divider
        class="border-opacity-100 mt-2"
        :class="{ 'mx-4': !smAndDown }"
        color="primary"
      />
    </div>

    <!-- Scan log -->
    <v-row
      ref="scan-log-ref"
      no-gutters
      class="scan-log overflow-y-scroll mb-4"
    >
      <v-col>
        <v-card elevation="0" class="bg-surface mx-auto mt-2" max-width="800">
          <v-card-text class="pa-0">
            <v-expansion-panels
              ref="expansion-panels-ref"
              v-model="panels"
              multiple
              flat
              variant="accordion"
            >
              <v-expansion-panel
                v-for="platform in scanningPlatforms"
                :key="platform.id"
              >
                <ScanPlatform :key="platform.id" :platform="platform" />
              </v-expansion-panel>
            </v-expansion-panels>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Scan stats -->
    <div
      v-if="scanningPlatforms.length > 0"
      class="text-caption position-sticky d-flex w-100 m-1 justify-center"
      style="bottom: 0.5rem"
    >
      <v-chip
        variant="outlined"
        color="toplayer"
        class="px-2 py-5 bg-background"
      >
        <v-chip
          color="primary"
          text-color="white"
          size="small"
          class="mr-1 my-1"
        >
          <v-icon left> mdi-controller </v-icon>
          <span v-if="xs" class="ml-2">{{
            t("scan.platforms-scanned-n", scanStats.scanned_platforms)
          }}</span>
          <span v-else class="ml-2">{{
            t("scan.platforms-scanned-with-details", {
              n_scanned_platforms: scanStats.scanned_platforms,
              n_total_platforms: scanStats.total_platforms,
              n_new_platforms: scanStats.new_platforms,
              n_identified_platforms: Math.min(
                scanStats.identified_platforms,
                scanStats.scanned_platforms,
              ),
            })
          }}</span>
        </v-chip>
        <v-chip
          color="primary"
          size="small"
          text-color="white"
          class="ml-1 my-1"
        >
          <v-icon left> mdi-disc </v-icon>
          <span v-if="xs" class="ml-2">{{
            t("scan.roms-scanned-n", scanStats.scanned_roms)
          }}</span>
          <span v-else class="ml-2">{{
            t("scan.roms-scanned-with-details", {
              n_scanned_roms: scanStats.scanned_roms,
              n_total_roms: scanStats.total_roms,
              n_new_roms: scanStats.new_roms,
              n_identified_roms: Math.min(
                scanStats.identified_roms,
                scanStats.scanned_roms,
              ),
            })
          }}</span>
        </v-chip>
      </v-chip>
    </div>
  </div>
</template>
<style lang="css">
.scan-log {
  scroll-behavior: smooth;
  /* margin-top: 10rem !important; */
}

.v-expansion-panel-text__wrapper {
  padding: 0px;
}
</style>
