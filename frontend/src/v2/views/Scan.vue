<script setup lang="ts">
// Scan — library scan control + live log. The socket listeners that push
// platforms/ROMs/firmware into `storeScanning` live in the shared
// `ScanBtn` navigation component (mounted app-wide), so this view is pure
// UI: read store state, render the log, emit scan/stop actions.
//
// The ScanPlatform expansion body is the v1 primitive — it's feature-scoped
// and fine to reuse inside a v2 panel until we rebuild it natively.
import { RAlert, RAvatar, RBtn, RIcon, RSelect, RSwitch } from "@v2/lib";
import { useLocalStorage } from "@vueuse/core";
import { storeToRefs } from "pinia";
import { computed, nextTick, ref, useTemplateRef, watch } from "vue";
import { useI18n } from "vue-i18n";
import { ROUTES } from "@/plugins/router";
import socket from "@/services/socket";
import storeConfig from "@/stores/config";
import storeHeartbeat, { type MetadataOption } from "@/stores/heartbeat";
import storePlatforms from "@/stores/platforms";
import storeScanning from "@/stores/scanning";
import ScanPlatform from "@/v2/components/Scan/ScanPlatform.vue";
import PlatformSelect from "@/v2/components/shared/PlatformSelect.vue";
import { useBackgroundArt } from "@/v2/composables/useBackgroundArt";
import { useBreakpoint } from "@/v2/composables/useBreakpoint";
import { useSocketEvent } from "@/v2/composables/useSocketEvent";

const LOCAL_STORAGE_METADATA_SOURCES_KEY = "scan.metadataSources";
const LOCAL_STORAGE_LAUNCHBOX_REMOTE_ENABLED_KEY =
  "scan.launchboxRemoteEnabled";
const { t } = useI18n();
const { xs } = useBreakpoint();
const scanningStore = storeScanning();
const { scanning, scanningPlatforms, scanStats } = storeToRefs(scanningStore);
const platformsStore = storePlatforms();
const { filteredPlatforms } = storeToRefs(platformsStore);
const configStore = storeConfig();
const { config } = storeToRefs(configStore);
const heartbeat = storeHeartbeat();
const platformsToScan = ref<number[]>([]);
// IDs of platforms whose ScanPlatform panel is currently open. We track
// by ID (not array index) because the order in `scanningPlatforms` can
// shift as new platforms arrive.
const openPlatforms = ref<Set<number>>(new Set());

function setOpen(platformId: number, open: boolean) {
  const next = new Set(openPlatforms.value);
  if (open) next.add(platformId);
  else next.delete(platformId);
  openPlatforms.value = next;
}
const scanLog = useTemplateRef<HTMLDivElement>("scan-log");

const setBgArt = useBackgroundArt();
setBgArt(null);

const sortedPlatforms = computed(() =>
  [...filteredPlatforms.value].sort((a, b) =>
    a.display_name.localeCompare(b.display_name),
  ),
);

const calculateHashes = computed(
  () => !config.value.SKIP_HASH_CALCULATION || false,
);

const metadataOptions = computed(() =>
  heartbeat.getMetadataOptionsByPriority().map((option) => {
    const requiresHashes = option.value === "hasheous" || option.value === "ra";
    const hashingDisabled = !calculateHashes.value;
    let disabled = option.disabled;
    if (hashingDisabled && requiresHashes) {
      if (option.value === "hasheous") {
        disabled = t("scan.hasheous-requires-hashes");
      } else if (option.value === "ra") {
        disabled = t("scan.retroachievements-requires-hashes");
      }
    }
    return { ...option, disabled };
  }),
);

const storedMetadataSources = useLocalStorage(
  LOCAL_STORAGE_METADATA_SOURCES_KEY,
  [] as string[],
);
const launchboxRemoteEnabled = useLocalStorage(
  LOCAL_STORAGE_LAUNCHBOX_REMOTE_ENABLED_KEY,
  true,
);
const metadataSources = ref<MetadataOption[]>(
  metadataOptions.value.filter(
    (m) => storedMetadataSources.value.includes(m.value) && !m.disabled,
  ) || heartbeat.getEnabledMetadataOptions(),
);

const isLaunchboxSelected = computed(() =>
  metadataSources.value.some((s) => s.value === "launchbox"),
);

watch(metadataOptions, (newOptions) => {
  metadataSources.value = metadataSources.value.filter((s) =>
    newOptions.some((opt) => opt.value === s.value && !opt.disabled),
  );
});

// Auto-expand panels when a platform first reports roms or firmware.
const platformsWithRomsKey = computed(() =>
  scanningPlatforms.value
    .map((p) => `${p.id}:${p.roms.length > 0 || p.firmware_count > 0 ? 1 : 0}`)
    .join(","),
);
watch(platformsWithRomsKey, () => {
  openPlatforms.value = new Set(
    scanningPlatforms.value
      .filter((p) => p.roms.length > 0 || p.firmware_count > 0)
      .map((p) => p.id),
  );
});

// Auto-scroll to bottom as new platforms arrive, unless the user scrolled up.
let userScrolledUp = false;
watch(
  () => scanningPlatforms.value.length,
  async () => {
    if (userScrolledUp) return;
    await nextTick();
    scanLog.value?.scrollTo({ top: scanLog.value.scrollHeight });
  },
);

function onScroll(e: Event) {
  const el = e.target as HTMLDivElement;
  userScrolledUp = el.scrollTop + el.clientHeight + 1 < el.scrollHeight;
}

type ScanType =
  | "new_platforms"
  | "quick"
  | "unmatched"
  | "update"
  | "hashes"
  | "complete";

const scanOptions: { title: string; subtitle: string; value: ScanType }[] = [
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
const scanType = ref<ScanType>("quick");

function scan() {
  scanningStore.setScanning(true);
  scanningPlatforms.value = [];

  if (!socket.connected) socket.connect();

  storedMetadataSources.value = metadataSources.value.map((s) => s.value);

  socket.emit("scan", {
    platforms: platformsToScan.value,
    type: scanType.value,
    apis: metadataSources.value.map((s) => s.value),
    launchbox_remote_enabled: launchboxRemoteEnabled.value,
  });
}

type ScanStatsPayload = typeof scanStats.value;
useSocketEvent<ScanStatsPayload>("scan:done", (stats) => {
  scanStats.value = stats;
});

function stopScan() {
  socket.emit("scan:stop");
}
</script>

<template>
  <section class="r-v2-scan">
    <header class="r-v2-scan__head">
      <div>
        <span class="r-v2-scan__eyebrow">
          <RIcon icon="mdi-magnify-scan" size="13" />
          Library
        </span>
        <h1 class="r-v2-scan__title">
          {{ t("scan.scan") }}
        </h1>
      </div>
      <RBtn
        variant="text"
        size="small"
        prepend-icon="mdi-table-cog"
        :to="{ name: ROUTES.LIBRARY_MANAGEMENT }"
      >
        {{ t("scan.manage-library") }}
      </RBtn>
    </header>

    <!-- Config panel -->
    <div class="r-v2-scan__config">
      <div class="r-v2-scan__fields">
        <PlatformSelect
          v-model="platformsToScan"
          :items="sortedPlatforms"
          :label="t('common.platforms')"
          prepend-inner-icon="mdi-controller"
          density="comfortable"
          :icon-size="32"
          multiple
          clearable
          hide-details
          chips
          show-meta
        />

        <RSelect
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
          <template #item="{ props: itemProps, item }">
            <li v-bind="itemProps">
              <RAvatar :image="item.raw.logo_path" size="22" rounded="sm" />
              <div class="r-select__item-stack">
                <div class="r-select__item-title">{{ item.raw.name }}</div>
                <div v-if="item.raw.disabled" class="r-select__item-subtitle">
                  {{ item.raw.disabled }}
                </div>
              </div>

              <div
                v-if="item.raw.value === 'launchbox'"
                class="r-v2-scan__lb-toggle"
              >
                <span
                  class="text-caption"
                  :class="{
                    'r-v2-scan__lb-inactive': launchboxRemoteEnabled,
                  }"
                >
                  Local
                </span>
                <RSwitch
                  v-model="launchboxRemoteEnabled"
                  :disabled="!isLaunchboxSelected"
                  @click.stop
                  @mousedown.stop
                />
                <span
                  class="text-caption"
                  :class="{
                    'r-v2-scan__lb-inactive': !launchboxRemoteEnabled,
                  }"
                >
                  Cloud
                </span>
              </div>
            </li>
          </template>
        </RSelect>

        <RSelect
          v-model="scanType"
          :items="scanOptions"
          :label="t('scan.scan-options')"
          prepend-inner-icon="mdi-magnify-scan"
          hide-details
          density="comfortable"
          variant="outlined"
        >
          <template #item="{ props: itemProps, item }">
            <li v-bind="itemProps">
              <div class="r-select__item-stack">
                <div class="r-select__item-title">{{ item.title }}</div>
                <div v-if="item.raw.subtitle" class="r-select__item-subtitle">
                  {{ item.raw.subtitle }}
                </div>
              </div>
            </li>
          </template>
        </RSelect>
      </div>

      <div class="r-v2-scan__actions">
        <RBtn
          size="large"
          variant="flat"
          color="primary"
          prepend-icon="mdi-magnify-scan"
          :loading="scanning"
          :disabled="scanning"
          @click="scan"
        >
          {{ t("scan.scan") }}
        </RBtn>
        <RBtn
          size="large"
          variant="outlined"
          color="error"
          prepend-icon="mdi-alert-octagon"
          :disabled="!scanning"
          @click="stopScan"
        >
          {{ t("scan.abort") }}
        </RBtn>
      </div>

      <div
        v-if="metadataSources.length === 0 || !calculateHashes"
        class="r-v2-scan__alerts"
      >
        <RAlert
          v-if="metadataSources.length === 0"
          type="warning"
          density="compact"
          :icon="false"
        >
          {{ t("scan.select-one-source") }}
        </RAlert>
        <RAlert
          v-if="!calculateHashes"
          type="warning"
          density="compact"
          :icon="false"
        >
          {{ t("scan.hash-calculation-disabled") }}
        </RAlert>
      </div>
    </div>

    <!-- Scan log -->
    <div ref="scan-log" class="r-v2-scan__log" @scroll="onScroll">
      <div v-if="scanningPlatforms.length === 0" class="r-v2-scan__empty">
        <RIcon icon="mdi-magnify-scan" size="48" />
        <p>
          {{
            scanning
              ? t("scan.scanning-library")
              : "Pick a scan configuration and hit Scan to begin."
          }}
        </p>
      </div>
      <div v-else class="r-v2-scan__panels">
        <ScanPlatform
          v-for="platform in scanningPlatforms"
          :key="platform.id"
          :platform="platform"
          :open="openPlatforms.has(platform.id)"
          class="r-v2-scan__panel"
          @update:open="(v) => setOpen(platform.id, v)"
        />
      </div>
    </div>

    <!-- Sticky stats bar -->
    <div v-if="scanningPlatforms.length > 0" class="r-v2-scan__stats">
      <div class="r-v2-scan__stat">
        <RIcon icon="mdi-controller" size="14" />
        <span v-if="xs">
          {{ t("scan.platforms-scanned-n", scanStats.scanned_platforms) }}
        </span>
        <span v-else>
          {{
            t("scan.platforms-scanned-with-details", {
              n_scanned_platforms: scanStats.scanned_platforms,
              n_total_platforms: scanStats.total_platforms,
              n_new_platforms: scanStats.new_platforms,
              n_identified_platforms: Math.min(
                scanStats.identified_platforms,
                scanStats.scanned_platforms,
              ),
            })
          }}
        </span>
      </div>
      <div class="r-v2-scan__stat">
        <RIcon icon="mdi-disc" size="14" />
        <span v-if="xs">
          {{ t("scan.roms-scanned-n", scanStats.scanned_roms) }}
        </span>
        <span v-else>
          {{
            t("scan.roms-scanned-with-details", {
              n_scanned_roms: scanStats.scanned_roms,
              n_total_roms: scanStats.total_roms,
              n_new_roms: scanStats.new_roms,
              n_identified_roms: Math.min(
                scanStats.identified_roms,
                scanStats.scanned_roms,
              ),
            })
          }}
        </span>
      </div>
      <div class="r-v2-scan__stat r-v2-scan__stat--alt">
        <RIcon icon="mdi-memory" size="14" />
        <span v-if="xs">
          {{ t("scan.firmware-scanned-n", scanStats.scanned_firmware) }}
        </span>
        <span v-else>
          {{
            t("scan.firmware-scanned-with-details", {
              n_scanned_firmware: scanStats.scanned_firmware,
              n_new_firmware: scanStats.new_firmware,
            })
          }}
        </span>
      </div>
    </div>
  </section>
</template>

<style scoped>
.r-v2-scan {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 24px var(--r-row-pad) 48px;
  min-height: calc(100vh - var(--r-nav-h));
  max-width: 1240px;
  margin: 0 auto;
  width: 100%;
}

.r-v2-scan__head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 12px;
}

.r-v2-scan__eyebrow {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-size: 10px;
  font-weight: var(--r-font-weight-semibold);
  color: var(--r-color-brand-primary);
  margin-bottom: 2px;
}

.r-v2-scan__title {
  margin: 0;
  font-size: var(--r-font-size-xl);
  font-weight: var(--r-font-weight-bold);
}

.r-v2-scan__config {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 18px;
  background: var(--r-color-bg-elevated);
  border: 1px solid var(--r-color-border);
  border-radius: var(--r-radius-lg);
  backdrop-filter: blur(18px);
  -webkit-backdrop-filter: blur(18px);
}

.r-v2-scan__fields {
  display: grid;
  grid-template-columns: 1.6fr 1.4fr 1fr;
  gap: 12px;
}

.r-v2-scan__actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.r-v2-scan__alerts {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.r-v2-scan__lb-toggle {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}
.r-v2-scan__lb-inactive {
  color: var(--r-color-fg-muted);
}

/* Scan log. Pins the chrome above and the stats bar below, with a
   scrollable middle that holds the platform expansion panels. */
.r-v2-scan__log {
  flex: 1;
  min-height: 240px;
  overflow-y: auto;
  scroll-behavior: smooth;
  background: var(--r-color-bg-elevated);
  border: 1px solid var(--r-color-border);
  border-radius: var(--r-radius-lg);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  padding: 6px;
}

.r-v2-scan__empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 48px 16px;
  color: var(--r-color-fg-muted);
  text-align: center;
}
.r-v2-scan__empty p {
  margin: 0;
  font-size: 13px;
  max-width: 360px;
}

.r-v2-scan__panels {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.r-v2-scan__panel {
  background: transparent;
}

/* Sticky stats row. */
.r-v2-scan__stats {
  position: sticky;
  bottom: 16px;
  align-self: center;
  display: inline-flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 8px 12px;
  background: color-mix(
    in srgb,
    var(--r-color-canvas-bg-deep) 85%,
    transparent
  );
  border: 1px solid var(--r-color-border-strong);
  border-radius: var(--r-radius-pill);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  box-shadow: 0 12px 28px color-mix(in srgb, black 45%, transparent);
  font-size: 12px;
  color: var(--r-color-fg);
}

.r-v2-scan__stat {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  background: color-mix(in srgb, var(--r-color-brand-primary) 18%, transparent);
  border-radius: var(--r-radius-pill);
  color: var(--r-color-brand-primary);
}
.r-v2-scan__stat--alt {
  background: color-mix(
    in srgb,
    var(--r-color-status-base-success) 18%,
    transparent
  );
  color: var(--r-color-success);
}

html[data-bp~="sm-and-down"] .r-v2-scan__fields {
  grid-template-columns: 1fr;
}
</style>
