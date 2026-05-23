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
//   Right — Live area: tall surface that shows either a welcoming
//           empty state (no scan started) or the streaming platform /
//           ROM list (scan in flight or just finished). Auto-expands
//           panels as ROMs arrive and auto-scrolls (within its own
//           scroll container) unless the user scrolled up. The card
//           owns its height so logs don't push the controls off-screen.
//
// Stats + abort live in `ScanStatsBar` — a floating bottom pill (same
// shell as Gallery's SelectionBar) so they don't push or compete with
// the content area. The pill slides up when a scan is active or after
// it finishes (until dismissed).
//
// Scan socket lifecycle (`scan:scanning_platform`, `scan:scanning_rom`,
// `scan:update_stats`, `scan:done`, `scan:done_ko`) is wired globally
// by `installScanLifecycle` in AppLayout; this view is pure UI.
//
// Hash matchers (Hasheous, Playmatch) sit between the provider select
// and the scan-type select as two compact switch pills. They're
// proxies — not standalone catalogs — and treating them as regular
// providers obscured that. Hasheous toggles its presence in the `apis`
// array (backend gate is `MetadataSource.HASHEOUS in apis`); Playmatch
// toggles a separate `playmatch_enabled` flag (it has no enum entry;
// backend gate is `playmatch_enabled and IGDB in apis`).
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
import ScanStatsBar from "@/v2/components/Scan/ScanStatsBar.vue";
import PlatformSelect from "@/v2/components/shared/PlatformSelect.vue";

const LOCAL_STORAGE_METADATA_SOURCES_KEY = "scan.metadataSources";
const LOCAL_STORAGE_LAUNCHBOX_REMOTE_ENABLED_KEY =
  "scan.launchboxRemoteEnabled";
const LOCAL_STORAGE_HASHEOUS_ENABLED_KEY = "scan.hasheousEnabled";
const LOCAL_STORAGE_PLAYMATCH_ENABLED_KEY = "scan.playmatchEnabled";

// Hash-matcher providers — proxies that match files by hash and feed
// IDs into the primary catalogs (IGDB, RetroAchievements). Kept out of
// the main provider select so users don't read them as standalone
// sources.
const HASH_MATCHER_KEYS = ["hasheous", "playmatch"] as const;

const { t } = useI18n();
const scanningStore = storeScanning();
const { scanning, scanningPlatforms } = storeToRefs(scanningStore);
const platformsStore = storePlatforms();
const { filteredPlatforms } = storeToRefs(platformsStore);
const configStore = storeConfig();
const { config } = storeToRefs(configStore);
const heartbeat = storeHeartbeat();
const platformsToScan = ref<number[]>([]);
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
  [...filteredPlatforms.value].sort((a, b) =>
    a.display_name.localeCompare(b.display_name),
  ),
);

const calculateHashes = computed(
  () => !config.value.SKIP_HASH_CALCULATION || false,
);

// Catalog options — main metadata sources. Hash matchers (hasheous,
// playmatch) are filtered out and rendered as switch pills. IGDB's
// heartbeat label flips to "IGDB + Playmatch" when Playmatch is
// admin-enabled — strip the suffix since Playmatch has its own tile.
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

// Auto-expand a platform's panel the moment it starts reporting roms
// or firmware. We track by `id:hasContent` so the watch fires only on
// the 0 → 1 transition, not per-ROM.
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

// Auto-scroll the live log as new platforms arrive, unless the user
// scrolled up to read an earlier panel.
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

// The start button is disabled while a scan runs OR when there's no
// metadata source picked (the scan wouldn't do anything useful).
const canStartScan = computed(
  () => !scanning.value && metadataSources.value.length > 0,
);

function scan() {
  // Reset stats + platform list so the navbar indicator and the stats
  // bar start at 0 instead of inheriting the previous scan's final
  // counters.
  scanningStore.reset();
  scanningStore.setScanning(true);
  scanningPlatforms.value = [];
  userScrolledUp = false;

  if (!socket.connected) socket.connect();

  storedMetadataSources.value = metadataSources.value.map((s) => s.value);

  // Build the apis payload: main catalogs + hasheous (when its switch
  // is on and the backend accepts it as a MetadataSource enum value).
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
  <div class="r-v2-scan">
    <!-- Teleport the section CTAs into the LibraryToolsLayout header.
         `defer` is load-bearing — see LibraryToolsLayout comments. -->
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

    <!-- Config card. The header (eyebrow + title + subtitle) tells the
         user what this section is for; the body holds the four inputs;
         the footer is the CTA + inline warnings. Locked (visually
         dimmed via .r-v2-scan-card--locked) while a scan runs so the
         user can read the running config without being tempted to
         edit it. -->
    <section
      class="r-v2-scan-card"
      :class="{ 'r-v2-scan-card--locked': scanning }"
      aria-labelledby="r-v2-scan-card-title"
    >
      <header class="r-v2-scan-card__head">
        <span class="r-v2-scan-card__eyebrow">
          <RIcon icon="mdi-cog-outline" size="12" />
          {{ t("scan.configure", "Configure scan") }}
        </span>
        <h2 id="r-v2-scan-card-title" class="r-v2-scan-card__title">
          {{ t("scan.title", "Library scan") }}
        </h2>
        <p class="r-v2-scan-card__subtitle">
          {{
            t(
              "scan.subtitle",
              "Discover new files, identify them against metadata sources, and refresh what you already have.",
            )
          }}
        </p>
      </header>

      <div class="r-v2-scan-card__fields">
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
          <template #chip="{ item }">
            <RTooltip :text="item.raw.name" location="bottom">
              <template #activator="{ props: tipProps }">
                <span
                  v-bind="tipProps"
                  class="r-v2-scan-card__provider-chip"
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
                <div class="r-select__item-title">
                  {{ item.raw.name }}
                </div>
                <div v-if="item.raw.disabled" class="r-select__item-subtitle">
                  {{ item.raw.disabled }}
                </div>
              </div>

              <div
                v-if="item.raw.value === 'launchbox'"
                class="r-v2-scan-card__lb-toggle"
              >
                <span
                  class="text-caption"
                  :class="{
                    'r-v2-scan-card__lb-inactive': launchboxRemoteEnabled,
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
                    'r-v2-scan-card__lb-inactive': !launchboxRemoteEnabled,
                  }"
                >
                  Cloud
                </span>
              </div>
            </li>
          </template>
        </RSelect>

        <!-- Hash-matcher switch pills. See header comment for the
             behaviour summary; the Info dialog covers what they do. -->
        <div
          class="r-v2-scan-card__matchers"
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
      </div>

      <footer class="r-v2-scan-card__cta">
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
          {{ scanning ? t("scan.scanning", "Scanning") : t("scan.scan") }}
        </RBtn>

        <div class="r-v2-scan-card__hints">
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
      </footer>
    </section>

    <!-- Live progress area. When nothing has scanned yet we paint a
         calm welcoming state; once platforms start arriving we render
         a vertical stack of expansion panels with a transition group
         so each card animates in. Owns its own scroll so logs never
         push the controls off-screen. -->
    <section class="r-v2-scan-live" aria-live="polite">
      <header class="r-v2-scan-live__head">
        <span
          class="r-v2-scan-live__pulse"
          :class="{
            'r-v2-scan-live__pulse--done':
              !scanning && scanningPlatforms.length > 0,
            'r-v2-scan-live__pulse--idle':
              !scanning && scanningPlatforms.length === 0,
          }"
        />
        <h3 class="r-v2-scan-live__title">
          {{
            scanning
              ? t("scan.live-progress", "Live progress")
              : scanningPlatforms.length > 0
                ? t("scan.scan-results", "Scan results")
                : t("scan.live-progress", "Live progress")
          }}
        </h3>
        <span v-if="scanningPlatforms.length > 0" class="r-v2-scan-live__count">
          {{ scanningPlatforms.length }}
          {{
            scanningPlatforms.length === 1
              ? t("common.platform", "platform")
              : t("common.platforms", "platforms")
          }}
        </span>
      </header>

      <div ref="scan-log" class="r-v2-scan-live__log" @scroll="onScroll">
        <div
          v-if="scanningPlatforms.length === 0"
          class="r-v2-scan-live__empty"
        >
          <div class="r-v2-scan-live__empty-orb">
            <RIcon icon="mdi-radar" size="56" />
          </div>
          <h4 class="r-v2-scan-live__empty-title">
            {{
              scanning
                ? t("scan.scanning-library", "Scanning your library…")
                : t("scan.empty-title", "Ready when you are")
            }}
          </h4>
          <p class="r-v2-scan-live__empty-hint">
            {{
              scanning
                ? t(
                    "scan.empty-hint-scanning",
                    "Platforms will appear here as the scanner discovers them.",
                  )
                : t(
                    "scan.empty-hint",
                    "Pick a scan configuration on the left and hit Start scan to see live progress here.",
                  )
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

    <!-- Floating stats / abort toolbar (SelectionBar shell pattern).
         Visibility and contents are owned by the component itself; we
         just emit the abort. -->
    <ScanStatsBar :scan-disabled="!scanning" @stop="stopScan" />
  </div>
</template>

<style scoped>
.r-v2-scan {
  /* Master/detail: controls left, live log right. `align-items: start`
     keeps the sticky behaviour intact — the left card sticks within
     its grid cell once the page scrolls past the layout's top padding.
     Reserve enough bottom space for the floating stats bar so the log
     card's last panel doesn't sit behind it. */
  display: grid;
  grid-template-columns: minmax(360px, 1fr) minmax(0, 1.6fr);
  gap: 18px;
  align-items: stretch;
  padding-bottom: 80px;
}

/* === Config card (left column) ================================ */
.r-v2-scan-card {
  position: sticky;
  /* Stick just below the fixed AppNav once the page scrolls. The 14px
     gap matches the breathing room above the card in the layout. */
  top: calc(var(--r-nav-h) + 14px);
  align-self: start;
  display: flex;
  flex-direction: column;
  gap: 18px;
  padding: 22px 22px 20px;
  background: var(--r-color-bg-elevated);
  border: 1px solid var(--r-color-border);
  border-radius: var(--r-radius-lg);
  backdrop-filter: blur(18px) saturate(140%);
  -webkit-backdrop-filter: blur(18px) saturate(140%);
  box-shadow:
    0 12px 30px color-mix(in srgb, black 24%, transparent),
    0 0 0 1px color-mix(in srgb, white 3%, transparent) inset;
  /* Subtle brand glow on the top edge — the visual cue that this is
     the action surface, not just another panel. */
  &::before {
    content: "";
    position: absolute;
    inset: 0;
    border-radius: inherit;
    pointer-events: none;
    background: linear-gradient(
      180deg,
      color-mix(in srgb, var(--r-color-brand-primary) 14%, transparent) 0%,
      transparent 64px
    );
    opacity: 0.65;
  }
  transition: opacity var(--r-motion-mid) var(--r-motion-ease-out);
}
.r-v2-scan-card--locked {
  /* Slight dim + pointer hold so the running scan reads as "in-flight,
     don't touch" without hiding the config. */
  opacity: 0.78;
}

.r-v2-scan-card__head {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.r-v2-scan-card__eyebrow {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  align-self: flex-start;
  padding: 4px 10px;
  border-radius: var(--r-radius-pill);
  background: color-mix(in srgb, var(--r-color-brand-primary) 16%, transparent);
  color: var(--r-color-brand-primary);
  font-size: 11px;
  font-weight: var(--r-font-weight-semibold);
  letter-spacing: 0.06em;
  text-transform: uppercase;
}
.r-v2-scan-card__title {
  margin: 4px 0 0;
  font-size: 22px;
  font-weight: var(--r-font-weight-bold);
  color: var(--r-color-fg);
  letter-spacing: -0.01em;
}
.r-v2-scan-card__subtitle {
  margin: 0;
  font-size: 13px;
  line-height: 1.5;
  color: var(--r-color-fg-muted);
  max-width: 70ch;
}

.r-v2-scan-card__fields {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.r-v2-scan-card__cta {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 10px;
}
.r-v2-scan-card__start {
  width: 100%;
}
.r-v2-scan-card__hints {
  display: flex;
  flex-direction: column;
  gap: 6px;
  width: 100%;
}

/* Provider chip — icon-only chip inside the RSelect chip slot. */
.r-v2-scan-card__provider-chip {
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.r-v2-scan-card__lb-toggle {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}
.r-v2-scan-card__lb-inactive {
  color: var(--r-color-fg-muted);
}

/* Hash matchers — compact pills sitting between provider + scan-type
   selects. Each pill is logo + small switch + tooltip; the Info
   dialog covers the meaning. In the stacked field layout they sit
   as a small row inside the column. */
.r-v2-scan-card__matchers {
  display: flex;
  flex-direction: row;
  align-items: center;
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

/* === Live area (right column) ================================ */
.r-v2-scan-live {
  position: sticky;
  top: calc(var(--r-nav-h) + 14px);
  align-self: start;
  display: flex;
  flex-direction: column;
  background: var(--r-color-bg-elevated);
  border: 1px solid var(--r-color-border);
  border-radius: var(--r-radius-lg);
  backdrop-filter: blur(18px) saturate(140%);
  -webkit-backdrop-filter: blur(18px) saturate(140%);
  box-shadow:
    0 12px 30px color-mix(in srgb, black 24%, transparent),
    0 0 0 1px color-mix(in srgb, white 3%, transparent) inset;
  overflow: hidden;
  /* Fill the viewport below the AppNav (with the LibraryToolsLayout
     padding + actions row + bottom clearance subtracted). The
     min-height floor keeps the card usable on short viewports — the
     page scrolls instead of squashing the log. */
  height: calc(100vh - var(--r-nav-h) - 220px);
  min-height: 540px;
}

.r-v2-scan-live__head {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 18px;
  border-bottom: 1px solid var(--r-color-border);
  flex-shrink: 0;
}
.r-v2-scan-live__title {
  margin: 0;
  font-size: 13px;
  font-weight: var(--r-font-weight-semibold);
  color: var(--r-color-fg);
  letter-spacing: 0.02em;
  text-transform: uppercase;
}
.r-v2-scan-live__count {
  margin-left: auto;
  font-size: 12px;
  color: var(--r-color-fg-muted);
  font-variant-numeric: tabular-nums;
}
/* Live indicator that mirrors the floating bar's pulse — consistency
   between the two scan-state surfaces. */
.r-v2-scan-live__pulse {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--r-color-brand-primary);
  box-shadow: 0 0 0 0
    color-mix(in srgb, var(--r-color-brand-primary) 65%, transparent);
  animation: r-v2-scan-live-pulse 1.6s ease-out infinite;
}
.r-v2-scan-live__pulse--done {
  background: var(--r-color-success);
  box-shadow: none;
  animation: none;
}
/* Calm grey dot when no scan has run yet — neither pulsing nor success. */
.r-v2-scan-live__pulse--idle {
  background: var(--r-color-fg-muted);
  box-shadow: none;
  animation: none;
}
@keyframes r-v2-scan-live-pulse {
  0% {
    box-shadow: 0 0 0 0
      color-mix(in srgb, var(--r-color-brand-primary) 65%, transparent);
  }
  100% {
    box-shadow: 0 0 0 10px
      color-mix(in srgb, var(--r-color-brand-primary) 0%, transparent);
  }
}
@media (prefers-reduced-motion: reduce) {
  .r-v2-scan-live__pulse {
    animation: none;
  }
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
  max-width: 420px;
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
  padding: 18px;
  gap: 14px;
}
html[data-bp~="sm-and-down"] .r-v2-scan-card__title {
  font-size: 19px;
}
</style>
