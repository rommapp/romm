<script setup lang="ts">
// Scan — library scan control + live log. The socket listeners that push
// platforms/ROMs/firmware/stats into `storeScanning` live in
// `installScanLifecycle`, wired in AppLayout, so this view is pure UI:
// read store state, render the log, emit scan/stop actions.
//
// Hash matchers (Hasheous, Playmatch) are extracted from the main
// metadata-source select and presented as a dedicated switch group below.
// They're proxies — not standalone catalogs — and treating them as
// regular providers obscured that. Hasheous toggles its presence in the
// `apis` array (backend gate is `MetadataSource.HASHEOUS in apis`).
// Playmatch toggles a separate `playmatch_enabled` flag (it has no enum
// entry; backend gate is `playmatch_enabled and IGDB in apis`).
import {
  RAlert,
  RAvatar,
  RBtn,
  RIcon,
  RSelect,
  RSwitch,
  RTooltip,
} from "@v2/lib";
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
import ScanInfoDialog from "@/v2/components/Scan/ScanInfoDialog.vue";
import ScanPlatform from "@/v2/components/Scan/ScanPlatform.vue";
import PlatformSelect from "@/v2/components/shared/PlatformSelect.vue";
import { useBreakpoint } from "@/v2/composables/useBreakpoint";

const LOCAL_STORAGE_METADATA_SOURCES_KEY = "scan.metadataSources";
const LOCAL_STORAGE_LAUNCHBOX_REMOTE_ENABLED_KEY =
  "scan.launchboxRemoteEnabled";
const LOCAL_STORAGE_HASHEOUS_ENABLED_KEY = "scan.hasheousEnabled";
const LOCAL_STORAGE_PLAYMATCH_ENABLED_KEY = "scan.playmatchEnabled";

// Hash-matcher providers — proxies that match files by hash and feed
// IDs into the primary catalogs (IGDB, RetroAchievements). Kept out of
// the main provider select so users don't read them as standalone
// sources. Order in the array drives the order in the switch group.
const HASH_MATCHER_KEYS = ["hasheous", "playmatch"] as const;
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

// Reference dialog — opened from the info button in the layout
// header (sibling of "Manage library"). Mounts the scan-type and
// metadata-provider lookup card.
const infoDialogOpen = ref(false);

const sortedPlatforms = computed(() =>
  [...filteredPlatforms.value].sort((a, b) =>
    a.display_name.localeCompare(b.display_name),
  ),
);

const calculateHashes = computed(
  () => !config.value.SKIP_HASH_CALCULATION || false,
);

// Catalog options — main metadata sources. Hash matchers (hasheous,
// playmatch) are filtered out and rendered in their own switch group.
// IGDB's heartbeat label flips to "IGDB + Playmatch" when Playmatch is
// admin-enabled — strip the suffix here since Playmatch now has its own
// switch tile.
const metadataOptions = computed(() =>
  heartbeat
    .getMetadataOptionsByPriority()
    .filter(
      (option) =>
        !(HASH_MATCHER_KEYS as readonly string[]).includes(option.value),
    )
    .map((option) => {
      const requiresHashes = option.value === "ra";
      const hashingDisabled = !calculateHashes.value;
      let disabled = option.disabled;
      if (hashingDisabled && requiresHashes) {
        disabled = t("scan.retroachievements-requires-hashes");
      }
      const name = option.value === "igdb" ? "IGDB" : option.name;
      return { ...option, name, disabled };
    }),
);

interface HashMatcher {
  value: "hasheous" | "playmatch";
  name: string;
  logo: string;
  /** Reason the switch is forced off, surfaced in the hover tooltip.
   *  null when the switch is interactable. */
  blockedReason: string | null;
  switchEnabled: boolean;
}

const hashMatchers = computed<HashMatcher[]>(() => {
  const sources = heartbeat.value.METADATA_SOURCES;
  const igdbSelected = metadataSources.value.some((s) => s.value === "igdb");
  const noHashes = !calculateHashes.value;

  const hasheousAdmin = Boolean(sources?.HASHEOUS_API_ENABLED);
  const playmatchAdmin = Boolean(sources?.PLAYMATCH_API_ENABLED);

  return [
    {
      value: "hasheous",
      name: "Hasheous",
      logo: "/assets/scrappers/hasheous.png",
      blockedReason: !hasheousAdmin
        ? t("scan.disabled-by-admin")
        : noHashes
          ? t("scan.hasheous-requires-hashes")
          : null,
      switchEnabled: hasheousAdmin && !noHashes,
    },
    {
      value: "playmatch",
      name: "Playmatch",
      logo: "/assets/scrappers/playmatch.png",
      blockedReason: !playmatchAdmin
        ? t("scan.disabled-by-admin")
        : !igdbSelected
          ? t(
              "scan.playmatch-requires-igdb",
              "Select IGDB to enable Playmatch.",
            )
          : null,
      switchEnabled: playmatchAdmin && igdbSelected,
    },
  ];
});

const storedMetadataSources = useLocalStorage(
  LOCAL_STORAGE_METADATA_SOURCES_KEY,
  [] as string[],
);
const launchboxRemoteEnabled = useLocalStorage(
  LOCAL_STORAGE_LAUNCHBOX_REMOTE_ENABLED_KEY,
  true,
);
// Hash-matcher switches persist independently of the main provider
// list so toggling them doesn't churn the localStorage entry that
// other dialogs (RefreshMetadataDialog) still read.
const hasheousEnabled = useLocalStorage(
  LOCAL_STORAGE_HASHEOUS_ENABLED_KEY,
  true,
);
const playmatchEnabled = useLocalStorage(
  LOCAL_STORAGE_PLAYMATCH_ENABLED_KEY,
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

function setHashMatcher(value: HashMatcher["value"], next: boolean) {
  if (value === "hasheous") hasheousEnabled.value = next;
  else playmatchEnabled.value = next;
}

function isHashMatcherOn(matcher: HashMatcher): boolean {
  if (!matcher.switchEnabled) return false;
  return matcher.value === "hasheous"
    ? hasheousEnabled.value
    : playmatchEnabled.value;
}

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
  // Reset stats + platform list so the navbar indicator and the stats
  // bar start at 0 instead of inheriting the previous scan's final
  // counters. Lifecycle (scan:done / scan:done_ko / scan:update_stats /
  // scan:scanning_platform / scan:scanning_rom) is handled globally by
  // `installScanLifecycle` in AppLayout.
  scanningStore.reset();
  scanningStore.setScanning(true);
  scanningPlatforms.value = [];

  if (!socket.connected) socket.connect();

  storedMetadataSources.value = metadataSources.value.map((s) => s.value);

  // Build the apis payload: main catalogs + hasheous (when its switch is
  // on and the backend accepts it as a MetadataSource enum value).
  // Playmatch has no enum entry — it's gated server-side via the
  // separate `playmatch_enabled` flag below.
  const apis = metadataSources.value.map((s) => s.value);
  const hasheousMatcher = hashMatchers.value.find(
    (m) => m.value === "hasheous",
  );
  if (hasheousMatcher && isHashMatcherOn(hasheousMatcher)) {
    apis.push("hasheous");
  }
  const playmatchMatcher = hashMatchers.value.find(
    (m) => m.value === "playmatch",
  );

  socket.emit("scan", {
    platforms: platformsToScan.value,
    type: scanType.value,
    apis,
    launchbox_remote_enabled: launchboxRemoteEnabled.value,
    playmatch_enabled: playmatchMatcher
      ? isHashMatcherOn(playmatchMatcher)
      : false,
  });
}

function stopScan() {
  socket.emit("scan:stop");
}
</script>

<template>
  <div class="r-v2-scan r-v2-section-stack">
    <!-- Teleport the section CTA into the LibraryToolsLayout header
         next to the title. The portal target lives in the layout.
         `defer` is load-bearing: when /scan is the entry route, the
         layout target #r-v2-lt-actions is not yet in the document at
         this view's mount time (Vue mounts children before inserting
         parent DOM). Without `defer`, querySelector returns null,
         Teleport stores a broken vnode, and the next navigation away
         crashes with "Cannot read properties of null (reading 'type'
         / 'parentNode')" during unmount. `defer` resolves the target
         on the next render tick, when the layout's DOM is in place. -->
    <Teleport to="#r-v2-lt-actions" defer>
      <RBtn
        prepend-icon="mdi-table-cog"
        :to="{ name: ROUTES.LIBRARY_MANAGEMENT }"
      >
        {{ t("common.library-management") }}
      </RBtn>
      <RBtn
        prepend-icon="mdi-information-outline"
        :aria-label="t('scan.info-dialog-title', 'Scan reference')"
        @click="infoDialogOpen = true"
      >
        {{ t("common.info", "Info") }}
      </RBtn>
    </Teleport>

    <ScanInfoDialog v-model="infoDialogOpen" />

    <!-- Config panel -->
    <div class="r-v2-scan__config">
      <div class="r-v2-scan__fields">
        <PlatformSelect
          v-model="platformsToScan"
          :items="sortedPlatforms"
          :label="t('common.platforms')"
          prepend-inner-icon="mdi-controller"
          density="compact"
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
          density="compact"
          multiple
          return-object
          clearable
          hide-details
          chips
          chip-tone="plain"
        >
          <!-- Icon-only chips — providers are visually distinctive by
               logo and the field is space-constrained, so the chip
               renders just the logo with a tooltip on hover. -->
          <template #chip="{ item }">
            <RTooltip :text="item.raw.name" location="bottom">
              <template #activator="{ props: tipProps }">
                <span
                  v-bind="tipProps"
                  class="r-v2-scan__provider-chip"
                  :aria-label="item.raw.name"
                >
                  <RAvatar :image="item.raw.logo_path" size="18" rounded="sm" />
                </span>
              </template>
            </RTooltip>
          </template>
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

        <!-- Hash matchers — Hasheous / Playmatch as compact switch
             pills between the provider and scan-type selects. They're
             proxies (hash → IGDB/RA), not standalone catalogs. Full
             explanation lives in the Info dialog (the "Metadata
             providers" tab covers both), so the inline UI stays terse:
             logo + tiny switch + tooltip with the name (and the
             blocked reason when the switch is forced off). -->
        <div
          class="r-v2-scan__matchers"
          role="group"
          aria-label="Hash matchers"
        >
          <RTooltip
            v-for="matcher in hashMatchers"
            :key="matcher.value"
            :text="
              matcher.blockedReason
                ? `${matcher.name} — ${matcher.blockedReason}`
                : matcher.name
            "
            location="bottom"
          >
            <template #activator="{ props: tipProps }">
              <div
                v-bind="tipProps"
                class="r-v2-scan__matcher"
                :class="{
                  'r-v2-scan__matcher--off': !matcher.switchEnabled,
                }"
              >
                <RAvatar
                  :image="matcher.logo"
                  size="16"
                  rounded="sm"
                  class="r-v2-scan__matcher-logo"
                />
                <RSwitch
                  size="small"
                  :model-value="isHashMatcherOn(matcher)"
                  :disabled="!matcher.switchEnabled"
                  :aria-label="matcher.name"
                  @update:model-value="(v) => setHashMatcher(matcher.value, v)"
                />
              </div>
            </template>
          </RTooltip>
        </div>

        <RSelect
          v-model="scanType"
          :items="scanOptions"
          :label="t('scan.scan-options')"
          prepend-inner-icon="mdi-magnify-scan"
          hide-details
          density="compact"
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
  </div>
</template>

<style scoped>
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
  /* 4 columns: platforms, providers, hash-matcher pills (auto-sized to
     the two switches placed side-by-side), scan type. The hash-matcher
     column shrinks to content so it doesn't steal space from the
     selects; the selects use `minmax(0, …)` so the chip rows inside
     them shrink instead of forcing the column to grow past its share. */
  grid-template-columns: minmax(0, 1.4fr) minmax(0, 1.1fr) auto minmax(0, 1fr);
  gap: 10px;
  align-items: center;
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

/* Provider chip — icon-only chip rendered inside the RSelect chip
   slot. Tight padding so it shrink-wraps to the logo + minimal frame. */
.r-v2-scan__provider-chip {
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

/* Hash matchers — two compact switch pills sitting on the same row as
   the selects, between the provider and scan-type selects. Each pill
   is just a logo + small switch; the Info dialog covers what they
   mean. Centred vertically against the (taller) selects. */
.r-v2-scan__matchers {
  display: inline-flex;
  flex-direction: row;
  align-items: center;
  gap: 6px;
  align-self: center;
}
.r-v2-scan__matcher {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 8px;
  border-radius: var(--r-radius-pill);
  background: var(--r-color-surface);
  border: 1px solid var(--r-color-border);
}
.r-v2-scan__matcher--off {
  opacity: 0.55;
}
.r-v2-scan__matcher-logo {
  background: var(--r-color-bg-elevated);
  flex-shrink: 0;
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
