<script setup lang="ts">
// Scan — library scan control + live log. Two-column master/detail
// layout (mirrors MatchRomBodyList):
//
//   Left  — Config card: glass panel with the four scan inputs
//           (platforms, providers, hash-matcher pills, scan type) plus
//           a prominent "Start scan" CTA. Inline warnings sit under
//           the CTA. While a scan runs, the inputs and button stay
//           visible but locked (disabled) — the user reads them as
//           the "what we're doing" summary. Sticks to the top of the
//           viewport when the page scrolls past it.
//
//   Right — Live area: tall surface that fills the viewport down to
//           the layout's bottom padding. Its header doubles as the
//           live status bar (pulse + label + per-class counter chips
//           + abort button + indeterminate/determinate progress bar
//           pinned to the bottom edge). The body shows either a
//           welcoming empty state (no scan started) or the streaming
//           platform / ROM list. Auto-expands panels as ROMs arrive
//           and auto-scrolls (within its own scroll container) unless
//           the user scrolled up.
//
// Scan socket lifecycle (`scan:scanning_platform`, `scan:scanning_rom`,
// `scan:update_stats`, `scan:done`, `scan:done_ko`) is wired globally
// by `installScanLifecycle` in AppLayout; this view is pure UI.
//
// The provider selects and the hash-matcher pills are driven by
// `useScanProviders`, shared with the two scan dialogs.
import {
  RAlert,
  RAvatar,
  RBtn,
  RIcon,
  RProgressLinear,
  RSelect,
  RSwitch,
  RTooltip,
} from "@v2/lib";
import { storeToRefs } from "pinia";
import { computed, nextTick, onMounted, ref, useTemplateRef, watch } from "vue";
import { useI18n } from "vue-i18n";
import { ROUTES } from "@/plugins/router";
import socket from "@/services/socket";
import storePlatforms from "@/stores/platforms";
import storeScanning from "@/stores/scanning";
import ScanInfoDialog from "@/v2/components/Scan/ScanInfoDialog.vue";
import ScanPlatform from "@/v2/components/Scan/ScanPlatform.vue";
import PlatformSelect from "@/v2/components/shared/PlatformSelect.vue";
import { useScanProviders } from "@/v2/composables/useScanProviders";
import { useScanTrigger } from "@/v2/composables/useScanTrigger";
import { scanNeedsMetadataSource, type ScanType } from "@/v2/types/scan";

const { t } = useI18n();
const { startScan } = useScanTrigger();
const scanningStore = storeScanning();
const { scanning, scanningPlatforms, scanStats } = storeToRefs(scanningStore);
const platformsStore = storePlatforms();
const { scannablePlatforms } = storeToRefs(platformsStore);
const platformsToScan = ref<string[]>([]);

// Never-scanned folders are fetched on demand.
onMounted(() => {
  platformsStore.fetchFilesystemPlatforms();
});
// IDs of platforms whose ScanPlatform panel is currently open.
const openPlatforms = ref<Set<number>>(new Set());

function setOpen(platformId: number, open: boolean) {
  const next = new Set(openPlatforms.value);
  if (open) next.add(platformId);
  else next.delete(platformId);
  openPlatforms.value = next;
}
const scanLog = useTemplateRef<HTMLDivElement>("scan-log");

const infoDialogOpen = ref(false);

const sortedPlatforms = computed(() =>
  [...scannablePlatforms.value].sort((a, b) =>
    a.display_name.localeCompare(b.display_name),
  ),
);

const {
  calculateHashes,
  generalProviders,
  specificProviders,
  metadataSources,
  effectiveMetadataSources,
  generalAllSelected,
  specificAllSelected,
  isLaunchboxSelected,
  launchboxRemoteEnabled,
  hashMatchers,
  setHashMatcher,
  isHashMatcherOn,
  buildScanPayload,
  persistSelection,
} = useScanProviders();

// Auto-expand a platform's panel the moment it starts reporting roms. The
// panel body only lists ROMs, so firmware alone leaves nothing to show. We
// track by `id:hasRoms` so the watch fires only on the 0 → 1 transition,
// not per-ROM.
const platformsWithRomsKey = computed(() =>
  scanningPlatforms.value
    .map((p) => `${p.id}:${p.roms.length > 0 ? 1 : 0}`)
    .join(","),
);
watch(platformsWithRomsKey, () => {
  openPlatforms.value = new Set(
    scanningPlatforms.value.filter((p) => p.roms.length > 0).map((p) => p.id),
  );
});

// Auto-scroll the live log as new platforms arrive, unless the user
// scrolled down to read an earlier panel. Newest platforms are prepended,
// so we keep the view pinned to the top.
let userScrolledDown = false;
watch(
  () => scanningPlatforms.value.length,
  async () => {
    if (userScrolledDown) return;
    await nextTick();
    scanLog.value?.scrollTo({ top: 0 });
  },
);
function onScroll(e: Event) {
  const el = e.target as HTMLDivElement;
  userScrolledDown = el.scrollTop > 1;
}

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

const needsMetadataSource = computed(() =>
  scanNeedsMetadataSource(scanType.value),
);
const canStartScan = computed(
  () =>
    !scanning.value &&
    (!needsMetadataSource.value || effectiveMetadataSources.value.length > 0),
);

// Live status header — pulled in from the (now retired) floating
// ScanStatsBar. Counters live in the scanning store; `total` lags
// `scanned` during platform discovery, so we clamp to avoid showing
// a >100% bar or counters that visually go backwards.
const liveStats = computed(() => {
  const platformsScanned = scanStats.value.scanned_platforms ?? 0;
  const platformsTotal = scanStats.value.total_platforms ?? 0;
  const platformsNew = scanStats.value.new_platforms ?? 0;
  const platformsIdentified = Math.min(
    scanStats.value.identified_platforms ?? 0,
    platformsScanned,
  );
  const romsScanned = scanStats.value.scanned_roms ?? 0;
  const romsTotal = scanStats.value.total_roms ?? 0;
  const romsNew = scanStats.value.new_roms ?? 0;
  const romsIdentified = Math.min(
    scanStats.value.identified_roms ?? 0,
    romsScanned,
  );
  const firmwareScanned = scanStats.value.scanned_firmware ?? 0;
  const firmwareNew = scanStats.value.new_firmware ?? 0;
  const romsUpdated = scanStats.value.updated_roms ?? 0;
  const filesNew = scanStats.value.new_files ?? 0;
  return {
    platforms: {
      scanned: platformsScanned,
      total: platformsTotal,
      new: platformsNew,
      identified: platformsIdentified,
    },
    roms: {
      scanned: romsScanned,
      total: romsTotal,
      new: romsNew,
      identified: romsIdentified,
    },
    firmware: { scanned: firmwareScanned, new: firmwareNew },
    files: { new: filesNew, updatedRoms: romsUpdated },
  };
});

const hasResults = computed(
  () => scanning.value || scanningPlatforms.value.length > 0,
);

const liveStatusLabel = computed(() => {
  if (scanning.value) return t("scan.scanning");
  if (scanningPlatforms.value.length > 0) return t("scan.scan-complete");
  return t("scan.live-progress");
});

// Progress bar — determinate once totals are known, indeterminate
// during initial platform discovery. Clamps to 100% so the bar never
// goes past full.
const progressTotal = computed(() =>
  Math.max(liveStats.value.roms.total, liveStats.value.roms.scanned),
);
const hasProgressTotal = computed(() => progressTotal.value > 0);
const progressValue = computed(() =>
  hasProgressTotal.value
    ? Math.min(100, (liveStats.value.roms.scanned / progressTotal.value) * 100)
    : 0,
);

function scan() {
  // Reset stats + platform list so the navbar indicator and the stats
  // bar start at 0 instead of inheriting the previous scan's final
  // counters.
  scanningStore.reset();
  scanningPlatforms.value = [];
  userScrolledDown = false;

  const started = startScan([
    {
      platform_fs_slugs: platformsToScan.value,
      type: scanType.value,
      ...buildScanPayload(),
    },
  ]);
  if (!started) return;

  persistSelection();
}

function stopScan() {
  socket.emit("scan:stop");
}
</script>

<template>
  <div class="r-v2-scan">
    <ScanInfoDialog v-model="infoDialogOpen" />

    <!-- Config card. Locked (visually dimmed via .r-v2-scan-card--locked)
         while a scan runs so the user can read the running config without
         being tempted to edit it. The info button is anchored top-right;
         the form fields stack vertically; the CTA + library management
         buttons sit in the footer below the form. -->
    <section
      class="r-v2-scan-card"
      :class="{ 'r-v2-scan-card--locked': scanning }"
      :aria-label="t('scan.title')"
    >
      <div class="r-v2-scan-card__head">
        <RBtn
          icon="mdi-information-outline"
          variant="text"
          size="small"
          :aria-label="t('scan.info-dialog-title')"
          @click="infoDialogOpen = true"
        />
      </div>

      <div class="r-v2-scan-card__fields">
        <!-- 1. Platform controls -->
        <section class="r-v2-scan-card__section">
          <h3 class="r-v2-scan-card__section-title">
            {{ t("scan.section-platforms") }}
          </h3>
          <PlatformSelect
            v-model="platformsToScan"
            :items="sortedPlatforms"
            item-key="fs_slug"
            :label="t('common.platforms')"
            prepend-inner-icon="mdi-controller"
            :icon-size="32"
            multiple
            clearable
            hide-details
            chips
            show-meta
            mark-unscanned
            :unscanned-label="t('scan.folder-not-scanned')"
            show-all-option
          />
        </section>

        <!-- 2. Metadata controls — providers (2.1) + proxies (2.2)
             share one section so it reads as "data we pull from
             external sources". -->
        <section class="r-v2-scan-card__section">
          <h3 class="r-v2-scan-card__section-title">
            {{ t("scan.section-metadata") }}
          </h3>

          <!-- 2.1 providers — two RSelects sharing the same
               `metadataSources` model, one per category. The
               primitive's `show-all-option` is subset-safe so the
               "All" toggle in one group only affects that group's
               items. -->
          <div class="r-v2-scan-card__subsection">
            <span class="r-v2-scan-card__subsection-label">
              {{ t("scan.section-providers") }}
            </span>

            <div class="r-v2-scan-card__providers-group">
              <span class="r-v2-scan-card__providers-group-label">
                {{ t("scan.section-providers-general") }}
              </span>
              <RSelect
                v-model="metadataSources"
                :items="generalProviders"
                :label="t('scan.section-providers-general')"
                item-title="name"
                prepend-inner-icon="mdi-database-search"
                variant="outlined"
                multiple
                return-object
                clearable
                hide-details
                chips
                chip-tone="plain"
                show-all-option
                @update:all-selected="generalAllSelected = $event"
              >
                <template #chip="{ item }">
                  <RTooltip :text="item.raw.name" location="bottom">
                    <template #activator="{ props: tipProps }">
                      <span
                        v-bind="tipProps"
                        class="r-v2-scan-card__provider-chip"
                        :aria-label="item.raw.name"
                      >
                        <RAvatar
                          :image="item.raw.logo_path"
                          size="18"
                          rounded="sm"
                        />
                      </span>
                    </template>
                  </RTooltip>
                </template>
                <template #item="{ props: itemProps, item }">
                  <li v-bind="itemProps">
                    <RAvatar
                      :image="item.raw.logo_path"
                      size="22"
                      rounded="sm"
                    />
                    <div class="r-select__item-stack">
                      <div class="r-select__item-title">
                        {{ item.raw.name }}
                      </div>
                      <div
                        v-if="item.raw.disabled"
                        class="r-select__item-subtitle"
                      >
                        {{ item.raw.disabled }}
                      </div>
                    </div>

                    <!-- LaunchBox: Local/Cloud inline toggle inside its
                       dropdown row. Disabled until LaunchBox itself
                       is selected. -->
                    <div
                      v-if="item.raw.value === 'launchbox'"
                      class="r-v2-scan-card__lb-toggle"
                      @click.stop
                      @mousedown.stop
                    >
                      <span
                        class="r-v2-scan-card__lb-label"
                        :class="{
                          'r-v2-scan-card__lb-inactive': launchboxRemoteEnabled,
                        }"
                      >
                        {{ t("rom.launchbox-local") }}
                      </span>
                      <RSwitch
                        v-model="launchboxRemoteEnabled"
                        :disabled="!isLaunchboxSelected"
                      />
                      <span
                        class="r-v2-scan-card__lb-label"
                        :class="{
                          'r-v2-scan-card__lb-inactive':
                            !launchboxRemoteEnabled,
                        }"
                      >
                        {{ t("rom.launchbox-cloud") }}
                      </span>
                    </div>
                  </li>
                </template>
              </RSelect>
            </div>

            <div
              v-if="specificProviders.length"
              class="r-v2-scan-card__providers-group"
            >
              <span class="r-v2-scan-card__providers-group-label">
                {{ t("scan.section-providers-specific") }}
              </span>
              <RSelect
                v-model="metadataSources"
                :items="specificProviders"
                :label="t('scan.section-providers-specific')"
                item-title="name"
                prepend-inner-icon="mdi-trophy-outline"
                variant="outlined"
                multiple
                return-object
                clearable
                hide-details
                chips
                chip-tone="plain"
                show-all-option
                @update:all-selected="specificAllSelected = $event"
              >
                <template #chip="{ item }">
                  <RTooltip :text="item.raw.name" location="bottom">
                    <template #activator="{ props: tipProps }">
                      <span
                        v-bind="tipProps"
                        class="r-v2-scan-card__provider-chip"
                        :aria-label="item.raw.name"
                      >
                        <RAvatar
                          :image="item.raw.logo_path"
                          size="18"
                          rounded="sm"
                        />
                      </span>
                    </template>
                  </RTooltip>
                </template>
                <template #item="{ props: itemProps, item }">
                  <li v-bind="itemProps">
                    <RAvatar
                      :image="item.raw.logo_path"
                      size="22"
                      rounded="sm"
                    />
                    <div class="r-select__item-stack">
                      <div class="r-select__item-title">
                        {{ item.raw.name }}
                      </div>
                      <div
                        v-if="item.raw.disabled"
                        class="r-select__item-subtitle"
                      >
                        {{ item.raw.disabled }}
                      </div>
                    </div>
                  </li>
                </template>
              </RSelect>
            </div>
          </div>

          <!-- 2.2 proxies (hash matchers) -->
          <div class="r-v2-scan-card__subsection">
            <span class="r-v2-scan-card__subsection-label">
              {{ t("scan.section-proxies") }}
            </span>
            <div
              class="r-v2-scan-card__matchers"
              role="group"
              :aria-label="t('scan.hash-matchers')"
            >
              <RTooltip
                v-for="matcher in hashMatchers"
                :key="matcher.value"
                :text="
                  matcher.blockedReason
                    ? `${matcher.name}: ${matcher.blockedReason}`
                    : matcher.name
                "
                location="bottom"
              >
                <template #activator="{ props: tipProps }">
                  <div
                    v-bind="tipProps"
                    class="r-v2-scan-card__matcher"
                    :class="{
                      'r-v2-scan-card__matcher--off': !matcher.switchEnabled,
                    }"
                  >
                    <RAvatar
                      :image="matcher.logo"
                      size="16"
                      rounded="sm"
                      class="r-v2-scan-card__matcher-logo"
                    />
                    <RSwitch
                      :model-value="isHashMatcherOn(matcher)"
                      :disabled="!matcher.switchEnabled"
                      :aria-label="matcher.name"
                      @update:model-value="
                        (v) => setHashMatcher(matcher.value, v)
                      "
                    />
                  </div>
                </template>
              </RTooltip>
            </div>
          </div>
        </section>

        <!-- 3. Scan type controls -->
        <section class="r-v2-scan-card__section">
          <h3 class="r-v2-scan-card__section-title">
            {{ t("scan.section-scan-type") }}
          </h3>
          <RSelect
            v-model="scanType"
            :items="scanOptions"
            :label="t('scan.scan-options')"
            prepend-inner-icon="mdi-magnify-scan"
            hide-details
            variant="outlined"
          >
            <template #item="{ props: itemProps, item }">
              <li v-bind="itemProps">
                <div class="r-select__item-stack">
                  <div class="r-select__item-title">
                    {{ item.title }}
                  </div>
                  <div v-if="item.raw.subtitle" class="r-select__item-subtitle">
                    {{ item.raw.subtitle }}
                  </div>
                </div>
              </li>
            </template>
          </RSelect>
        </section>
      </div>

      <!-- 4. Action buttons — untitled; the divider above marks the
           boundary between "config" and "actions" without a label. -->
      <footer class="r-v2-scan-card__section r-v2-scan-card__cta">
        <div class="r-v2-scan-card__hints">
          <RAlert
            v-if="needsMetadataSource && effectiveMetadataSources.length === 0"
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
            <span class="r-v2-scan-card__hash-alert">
              {{ t("scan.hash-calculation-disabled") }}
              <RTooltip location="bottom">
                <template #activator="{ props: tipProps }">
                  <RIcon
                    v-bind="tipProps"
                    icon="mdi-information-outline"
                    size="14"
                    class="r-v2-scan-card__hash-info"
                  />
                </template>
                <span
                  class="r-v2-scan-card__hash-info-text"
                  v-html="t('scan.hashes-disabled-tooltip')"
                />
              </RTooltip>
            </span>
          </RAlert>
        </div>

        <RBtn
          class="r-v2-scan-card__start"
          size="large"
          variant="flat"
          color="primary"
          prepend-icon="mdi-magnify-scan"
          :loading="scanning"
          :disabled="!canStartScan"
          @click="scan"
        >
          {{ scanning ? t("scan.scanning") : t("scan.scan") }}
        </RBtn>

        <RBtn
          class="r-v2-scan-card__library"
          variant="outlined"
          prepend-icon="mdi-table-cog"
          :to="{ name: ROUTES.LIBRARY_MANAGEMENT }"
        >
          {{ t("common.library-management") }}
        </RBtn>
      </footer>
    </section>

    <!-- Live progress area. When nothing has scanned yet we paint a
         calm welcoming state; once platforms start arriving we render
         a vertical stack of expansion panels with a transition group
         so each card animates in. Owns its own scroll so logs never
         push the controls off-screen. -->
    <section class="r-v2-scan-live" aria-live="polite">
      <header class="r-v2-scan-live__head">
        <div class="r-v2-scan-live__status">
          <span v-if="scanning" class="r-v2-scan-live__pulse" />
          <span class="r-v2-scan-live__status-label">
            {{ liveStatusLabel }}
          </span>
        </div>

        <div v-if="hasResults" class="r-v2-scan-live__counters">
          <RTooltip
            :text="
              t('scan.platforms-scanned-with-details', {
                n_scanned_platforms: liveStats.platforms.scanned,
                n_total_platforms: liveStats.platforms.total,
                n_new_platforms: liveStats.platforms.new,
                n_identified_platforms: liveStats.platforms.identified,
              })
            "
            location="bottom"
          >
            <template #activator="{ props: tipProps }">
              <span v-bind="tipProps" class="r-v2-scan-live__chip">
                <RIcon icon="mdi-controller" size="14" />
                <span class="r-v2-scan-live__chip-num">
                  {{ liveStats.platforms.scanned }}
                </span>
                <span
                  v-if="liveStats.platforms.total"
                  class="r-v2-scan-live__chip-den"
                >
                  /{{ liveStats.platforms.total }}
                </span>
              </span>
            </template>
          </RTooltip>

          <RTooltip
            :text="
              t('scan.roms-scanned-with-details', {
                n_scanned_roms: liveStats.roms.scanned,
                n_total_roms: liveStats.roms.total,
                n_new_roms: liveStats.roms.new,
                n_identified_roms: liveStats.roms.identified,
              })
            "
            location="bottom"
          >
            <template #activator="{ props: tipProps }">
              <span v-bind="tipProps" class="r-v2-scan-live__chip">
                <RIcon icon="mdi-disc" size="14" />
                <span class="r-v2-scan-live__chip-num">
                  {{ liveStats.roms.scanned }}
                </span>
                <span
                  v-if="liveStats.roms.total"
                  class="r-v2-scan-live__chip-den"
                >
                  /{{ liveStats.roms.total }}
                </span>
              </span>
            </template>
          </RTooltip>

          <RTooltip
            v-if="liveStats.firmware.scanned > 0"
            :text="
              t('scan.firmware-scanned-with-details', {
                n_scanned_firmware: liveStats.firmware.scanned,
                n_new_firmware: liveStats.firmware.new,
              })
            "
            location="bottom"
          >
            <template #activator="{ props: tipProps }">
              <span
                v-bind="tipProps"
                class="r-v2-scan-live__chip r-v2-scan-live__chip--alt"
              >
                <RIcon icon="mdi-memory" size="14" />
                <span class="r-v2-scan-live__chip-num">
                  {{ liveStats.firmware.scanned }}
                </span>
              </span>
            </template>
          </RTooltip>
          <RTooltip
            v-if="liveStats.files.new > 0 || liveStats.files.updatedRoms > 0"
            :text="
              t('scan.files-scanned-with-details', {
                n_new_files: liveStats.files.new,
                n_updated_roms: liveStats.files.updatedRoms,
              })
            "
            location="bottom"
          >
            <template #activator="{ props: tipProps }">
              <span
                v-bind="tipProps"
                class="r-v2-scan-live__chip r-v2-scan-live__chip--alt"
              >
                <RIcon icon="mdi-file-plus-outline" size="14" />
                <span class="r-v2-scan-live__chip-num">
                  {{ liveStats.files.new }}
                </span>
              </span>
            </template>
          </RTooltip>
        </div>

        <div v-if="scanning" class="r-v2-scan-live__actions">
          <RTooltip :text="t('scan.abort-scan')" location="bottom">
            <template #activator="{ props: tipProps }">
              <RBtn
                v-bind="tipProps"
                icon="mdi-stop-circle-outline"
                variant="text"
                color="danger"
                size="small"
                :aria-label="t('scan.abort-scan')"
                @click="stopScan"
              />
            </template>
          </RTooltip>
        </div>

        <RProgressLinear
          v-if="scanning"
          class="r-v2-scan-live__progress"
          :indeterminate="!hasProgressTotal"
          :model-value="progressValue"
          :height="2"
          color="primary"
          :rounded="false"
        />
      </header>

      <div ref="scan-log" class="r-v2-scan-live__log" @scroll="onScroll">
        <div
          v-if="scanningPlatforms.length === 0"
          class="r-v2-scan-live__empty"
        >
          <div class="r-v2-scan-live__empty-orb">
            <RIcon icon="mdi-radar" size="56" />
          </div>
          <p class="r-v2-scan-live__empty-hint">
            {{
              scanning ? t("scan.empty-hint-scanning") : t("scan.empty-hint")
            }}
          </p>
        </div>

        <TransitionGroup
          v-else
          name="r-v2-scan-panel"
          tag="div"
          class="r-v2-scan-live__panels"
        >
          <ScanPlatform
            v-for="platform in scanningPlatforms"
            :key="platform.id"
            :platform="platform"
            :open="openPlatforms.has(platform.id)"
            class="r-v2-scan-live__panel"
            @update:open="(v) => setOpen(platform.id, v)"
          />
        </TransitionGroup>
      </div>
    </section>
  </div>
</template>

<style scoped>
.r-v2-scan {
  /* Master/detail: controls left, live log right. `align-items: start`
     keeps the sticky behaviour intact — the left card sticks within
     its grid cell once the page scrolls past the layout's top padding. */
  display: grid;
  grid-template-columns: minmax(360px, 1fr) minmax(0, 1.6fr);
  gap: 18px;
  align-items: stretch;
}

/* === Config card (left column) ================================
   Surface vocabulary matches the SettingsSection body used across
   Profile / Settings: solid `--r-color-bg-elevated`, plain border,
   no blur / no shadow / no gradient overlay. */
.r-v2-scan-card {
  position: sticky;
  /* Stick just below the fixed AppNav once the page scrolls. The 14px
     gap matches the breathing room above the card in the layout. */
  top: calc(var(--r-nav-h) + 14px);
  align-self: start;
  display: flex;
  flex-direction: column;
  gap: 18px;
  padding: 16px 18px 18px;
  background: var(--r-color-bg-elevated);
  border: 1px solid var(--r-color-border);
  border-radius: var(--r-radius-lg);
  transition: opacity var(--r-motion-mid) var(--r-motion-ease-out);
}
.r-v2-scan-card--locked {
  /* Slight dim + pointer hold so the running scan reads as "in-flight,
     don't touch" without hiding the config. */
  opacity: 0.78;
}

/* Top row — info button anchored top-right above the platform select. */
.r-v2-scan-card__head {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  min-height: 0;
  margin-bottom: -8px;
}

.r-v2-scan-card__fields {
  display: flex;
  flex-direction: column;
  /* Matches the parent card's 18px gap so every divider — between
     fields-internal sections AND between __fields/__cta — has the
     same breathing room above and below. */
  gap: 18px;
}

/* Each numbered section in the config card: small uppercase label
   above its content, divided from the next section by a hairline
   border-top. The first section inside `__fields` drops the border
   so the head row doesn't sit under a stray line; the `__cta` footer
   keeps its border because it sits below `__fields` and the divider
   separates "configuration" from "actions". */
.r-v2-scan-card__section {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding-top: 14px;
  border-top: 1px solid var(--r-color-border);
}
.r-v2-scan-card__section:first-child {
  padding-top: 0;
  border-top: 0;
}
.r-v2-scan-card__section-title {
  margin: 0;
  font-size: 11px;
  font-weight: var(--r-font-weight-semibold);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--r-color-fg-muted);
}

/* Sub-section inside Metadata (providers / proxies). Tightly spaced
   so they read as siblings of the same section, separated by a small
   muted label rather than a divider. */
.r-v2-scan-card__subsection {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.r-v2-scan-card__subsection-label {
  font-size: 10.5px;
  font-weight: var(--r-font-weight-medium);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--r-color-fg-faint);
}

.r-v2-scan-card__cta {
  align-items: stretch;
  gap: 8px;
}
.r-v2-scan-card__start {
  width: 100%;
}
.r-v2-scan-card__library {
  width: 100%;
}
.r-v2-scan-card__hints {
  display: flex;
  flex-direction: column;
  gap: 6px;
  width: 100%;
}
.r-v2-scan-card__hints:empty {
  display: none;
}
.r-v2-scan-card__hash-alert {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.r-v2-scan-card__hash-info {
  cursor: help;
  color: var(--r-color-warning);
  opacity: 0.85;
  transition: opacity var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-v2-scan-card__hash-info:hover {
  opacity: 1;
}

/* Providers split into General / Specific groups. Each group has a
   tiny inline caption above its RSelect — same visual rhythm as the
   subsection label, indented one level deeper. */
.r-v2-scan-card__providers-group {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.r-v2-scan-card__providers-group + .r-v2-scan-card__providers-group {
  margin-top: 8px;
}
.r-v2-scan-card__providers-group-label {
  font-size: 10px;
  font-weight: var(--r-font-weight-medium);
  letter-spacing: 0.04em;
  color: var(--r-color-fg-faint);
}

/* Provider chip in the activator — icon-only avatar so a multi-select
   doesn't drown the field in coloured pills. The `#chip` slot renders
   into RSelect's RTag. */
.r-v2-scan-card__provider-chip {
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

/* Hash-matcher proxies — compact icon + switch pills (kept as direct
   pills since there are only two and a select would be overkill). */
.r-v2-scan-card__matchers {
  display: flex;
  flex-direction: row;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  align-self: flex-start;
}
.r-v2-scan-card__matcher {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 8px;
  border-radius: var(--r-radius-pill);
  background: var(--r-color-surface);
  border: 1px solid var(--r-color-border);
}
.r-v2-scan-card__matcher--off {
  opacity: 0.55;
}
.r-v2-scan-card__matcher-logo {
  background: var(--r-color-bg-elevated);
  flex-shrink: 0;
}

/* LaunchBox Local/Cloud toggle inline inside its dropdown item. */
.r-v2-scan-card__lb-toggle {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-left: auto;
}
.r-v2-scan-card__lb-label {
  font-size: 11px;
  color: var(--r-color-fg);
  white-space: nowrap;
}
.r-v2-scan-card__lb-inactive {
  color: var(--r-color-fg-muted);
}

/* === Live area (right column) ================================
   Same flat surface vocabulary as the config card (Profile-style).
   Header doubles as the live status panel (pulse + label + counters
   + abort + progress bar). The card fills from `nav-h + top gap`
   down to the SettingsLayout's bottom padding. */
.r-v2-scan-live {
  position: sticky;
  top: calc(var(--r-nav-h) + 14px);
  align-self: start;
  display: flex;
  flex-direction: column;
  background: var(--r-color-bg-elevated);
  border: 1px solid var(--r-color-border);
  border-radius: var(--r-radius-lg);
  overflow: hidden;
  /* SettingsLayout's content column adds 32px top + 60px bottom padding
     around the grid; AppLayout main reserves --r-nav-h for the fixed
     navbar. Subtracting (nav + 92) keeps the column flush with the
     available viewport so the page itself never scrolls. */
  height: calc(100vh - var(--r-nav-h) - 92px);
  min-height: 540px;
}

/* Header — three columns (status / counters / actions) with a
   progress bar pinned to the bottom edge. Layout is grid-based so
   the status label / counter chip widths can fluctuate without the
   actions slot drifting. */
.r-v2-scan-live__head {
  position: relative;
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: center;
  column-gap: 14px;
  padding: 12px 16px;
  border-bottom: 1px solid var(--r-color-border);
  flex-shrink: 0;
  min-height: 56px;
}

.r-v2-scan-live__status {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: var(--r-font-weight-semibold);
  color: var(--r-color-brand-primary);
  white-space: nowrap;
  min-width: 132px;
}
.r-v2-scan-live__status-label {
  letter-spacing: 0.02em;
}

/* Pulse — shown only while actively scanning. */
.r-v2-scan-live__pulse {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--r-color-brand-primary);
  box-shadow: 0 0 0 0
    color-mix(in srgb, var(--r-color-brand-primary) 65%, transparent);
  animation: r-v2-scan-live-pulse 1.6s ease-out infinite;
}
@keyframes r-v2-scan-live-pulse {
  0% {
    box-shadow: 0 0 0 0
      color-mix(in srgb, var(--r-color-brand-primary) 65%, transparent);
  }
  100% {
    box-shadow: 0 0 0 12px
      color-mix(in srgb, var(--r-color-brand-primary) 0%, transparent);
  }
}
@media (prefers-reduced-motion: reduce) {
  .r-v2-scan-live__pulse {
    animation: none;
  }
}

/* Counter chips — sit in the middle grid track, right-aligned against
   the actions. Each chip has a min-width so 1 → 2 → 3-digit transitions
   don't reflow neighbouring chips. */
.r-v2-scan-live__counters {
  display: inline-flex;
  align-items: center;
  justify-content: flex-end;
  gap: 6px;
  min-width: 0;
}
.r-v2-scan-live__chip {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  padding: 4px 10px;
  border-radius: var(--r-radius-pill);
  background: color-mix(in srgb, var(--r-color-brand-primary) 18%, transparent);
  color: var(--r-color-brand-primary);
  font-size: 12px;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
  min-width: 64px;
}
.r-v2-scan-live__chip--alt {
  background: color-mix(
    in srgb,
    var(--r-color-status-base-success) 18%,
    transparent
  );
  color: var(--r-color-success);
}
.r-v2-scan-live__chip-num {
  font-weight: var(--r-font-weight-semibold);
}
.r-v2-scan-live__chip-den {
  opacity: 0.7;
}

.r-v2-scan-live__actions {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 36px;
}

/* Progress bar — pinned to the bottom edge of the header so it reads
   as the boundary between "what's happening" and "what's been done". */
.r-v2-scan-live__progress {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
}

.r-v2-scan-live__log {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  scroll-behavior: smooth;
  padding: 12px;
}

/* Empty state — calm, centred, brand-orbed icon. The orb provides the
   focal point so the panel doesn't read as a featureless rectangle. */
.r-v2-scan-live__empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 56px 24px 64px;
  color: var(--r-color-fg-muted);
  text-align: center;
  min-height: 280px;
}
.r-v2-scan-live__empty-orb {
  display: grid;
  place-items: center;
  width: 96px;
  height: 96px;
  border-radius: 50%;
  background: radial-gradient(
    circle at 30% 30%,
    color-mix(in srgb, var(--r-color-brand-primary) 28%, transparent) 0%,
    color-mix(in srgb, var(--r-color-brand-primary) 8%, transparent) 60%,
    transparent 100%
  );
  color: var(--r-color-brand-primary);
  margin-bottom: 4px;
}
.r-v2-scan-live__empty-title {
  margin: 0;
  font-size: 17px;
  font-weight: var(--r-font-weight-semibold);
  color: var(--r-color-fg);
}
.r-v2-scan-live__empty-hint {
  margin: 0;
  font-size: 13px;
  line-height: 1.55;
  max-width: 600px;
}

.r-v2-scan-live__panels {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.r-v2-scan-live__panel {
  background: transparent;
}

/* TransitionGroup entrance — slide-in from below + fade. Cards that
   are already on screen stay put; only new arrivals animate. */
.r-v2-scan-panel-enter-active {
  transition:
    opacity var(--r-motion-mid) var(--r-motion-ease-out),
    transform var(--r-motion-mid) var(--r-motion-ease-back);
}
.r-v2-scan-panel-enter-from {
  opacity: 0;
  transform: translateY(12px);
}
.r-v2-scan-panel-leave-active {
  transition:
    opacity var(--r-motion-fast) var(--r-motion-ease-out),
    transform var(--r-motion-fast) var(--r-motion-ease-out);
  position: absolute;
}
.r-v2-scan-panel-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}
@media (prefers-reduced-motion: reduce) {
  .r-v2-scan-panel-enter-active,
  .r-v2-scan-panel-leave-active {
    transition: none;
  }
  .r-v2-scan-panel-enter-from,
  .r-v2-scan-panel-leave-to {
    transform: none;
  }
}

/* === Responsive ============================================== */
/* Below `md` the two columns stack: controls on top, log below. Drop
   sticky positioning so the cards flow naturally with the page. The
   log keeps an internal scroll but with a shorter min-height so it
   doesn't dominate small viewports. */
html[data-bp~="md-and-down"] .r-v2-scan {
  grid-template-columns: 1fr;
}
html[data-bp~="md-and-down"] .r-v2-scan-card,
html[data-bp~="md-and-down"] .r-v2-scan-live {
  position: static;
}
html[data-bp~="md-and-down"] .r-v2-scan-live {
  height: auto;
  min-height: 420px;
  max-height: calc(100vh - var(--r-nav-h) - 160px);
}

html[data-bp~="sm-and-down"] .r-v2-scan-card__matchers {
  align-self: flex-start;
}
html[data-bp~="sm-and-down"] .r-v2-scan-card {
  padding: 14px;
  gap: 14px;
}

/* On xs, the status label takes too much width — collapse it and let
   the counter chips claim the row. */
html[data-bp~="xs"] .r-v2-scan-live__status {
  min-width: 0;
}
html[data-bp~="xs"] .r-v2-scan-live__status-label {
  display: none;
}
</style>
