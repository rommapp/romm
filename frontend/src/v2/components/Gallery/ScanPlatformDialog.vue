<script setup lang="ts">
// ScanPlatformDialog — kicks off a scan for a single platform with
// the user's choice of providers, hash-matchers, and scan type.
//
// Visual + interaction language mirrors `RefreshMetadataDialog`
// (provider selects split into General / Specific, hash-matcher
// proxies as switch pills, scan-type select), but the identity row
// at the top shows the platform instead of a ROM, and the scan-type
// list mirrors the Scan view's per-platform options (no "new
// platforms" — that's a discovery scan against the whole library,
// not a single platform).
import {
  RAlert,
  RAvatar,
  RBtn,
  RDialog,
  RPlatformIcon,
  RSelect,
  RSwitch,
  RTooltip,
} from "@v2/lib";
import { useLocalStorage } from "@vueuse/core";
import { storeToRefs } from "pinia";
import { computed, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import socket from "@/services/socket";
import storeConfig from "@/stores/config";
import storeHeartbeat, { type MetadataOption } from "@/stores/heartbeat";
import type { Platform } from "@/stores/platforms";
import storeScanning from "@/stores/scanning";
import { useSnackbar } from "@/v2/composables/useSnackbar";

defineOptions({ inheritAttrs: false });

const props = defineProps<{
  modelValue: boolean;
  platform: Platform;
}>();

const emit = defineEmits<{
  (e: "update:modelValue", v: boolean): void;
}>();

const LOCAL_STORAGE_METADATA_SOURCES_KEY = "scan.metadataSources";
const LOCAL_STORAGE_LAUNCHBOX_REMOTE_ENABLED_KEY =
  "scan.launchboxRemoteEnabled";
const LOCAL_STORAGE_HASHEOUS_ENABLED_KEY = "scan.hasheousEnabled";
const LOCAL_STORAGE_PLAYMATCH_ENABLED_KEY = "scan.playmatchEnabled";

// Hash-matcher providers — proxies that match files by hash and feed
// IDs into the primary catalogs. Filtered out of the main provider
// select and rendered as switch pills so users don't read them as
// standalone sources.
const HASH_MATCHER_KEYS = ["hasheous", "playmatch"] as const;

const GENERAL_PROVIDER_KEYS = new Set([
  "igdb",
  "ss",
  "moby",
  "launchbox",
  "flashpoint",
  "gamelist",
  "libretro",
]);
const SPECIFIC_PROVIDER_KEYS = new Set(["ra", "sgdb", "hltb"]);

const { t } = useI18n();
const snackbar = useSnackbar();
const heartbeat = storeHeartbeat();
const scanningStore = storeScanning();
const configStore = storeConfig();
const { config } = storeToRefs(configStore);

const calculateHashes = computed(() => !config.value.SKIP_HASH_CALCULATION);

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
        disabled = t("scan.requires-hashes", { source: option.name });
      }
      const name = option.value === "igdb" ? "IGDB" : option.name;
      return { ...option, name, disabled };
    }),
);

const generalProviders = computed<MetadataOption[]>(() =>
  metadataOptions.value.filter((o) => GENERAL_PROVIDER_KEYS.has(o.value)),
);
const specificProviders = computed<MetadataOption[]>(() =>
  metadataOptions.value.filter((o) => SPECIFIC_PROVIDER_KEYS.has(o.value)),
);

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

const metadataSources = ref<MetadataOption[]>([]);
const isLaunchboxSelected = computed(() =>
  metadataSources.value.some((s) => s.value === "launchbox"),
);

watch(
  [metadataOptions, storedMetadataSources],
  ([newOptions, newStoredMetadataSources]) => {
    const filteredMetadataSources = newOptions.filter(
      (option) =>
        newStoredMetadataSources.includes(option.value) && !option.disabled,
    );
    metadataSources.value =
      filteredMetadataSources.length > 0
        ? filteredMetadataSources
        : heartbeat
            .getEnabledMetadataOptions()
            .filter(
              (o) =>
                !(HASH_MATCHER_KEYS as readonly string[]).includes(o.value),
            );
  },
  { immediate: true },
);

interface HashMatcher {
  value: "hasheous" | "playmatch";
  name: string;
  logo: string;
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
          ? t("scan.requires-hashes", { source: "Hasheous" })
          : null,
      switchEnabled: hasheousAdmin && !noHashes,
    },
    {
      value: "playmatch",
      name: "Playmatch",
      logo: "/assets/scrappers/playmatch.png",
      blockedReason: !playmatchAdmin
        ? t("scan.disabled-by-admin")
        : noHashes
          ? t("scan.requires-hashes", { source: "Playmatch" })
          : !igdbSelected
            ? t(
                "scan.playmatch-requires-igdb",
                "Select IGDB to enable Playmatch.",
              )
            : null,
      switchEnabled: playmatchAdmin && !noHashes && igdbSelected,
    },
  ];
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

// Per-platform scan types — the full Scan-view list minus
// `new_platforms` (a discovery scan against fs_slugs not yet in the
// DB, which can't be scoped to a known platform).
type ScanType = "quick" | "unmatched" | "update" | "hashes" | "complete";

const scanOptions = computed<
  { title: string; subtitle: string; value: ScanType }[]
>(() => [
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
]);
const scanType = ref<ScanType>("quick");

function closeDialog() {
  emit("update:modelValue", false);
}

function onScan() {
  scanningStore.setScanning(true);
  storedMetadataSources.value = metadataSources.value.map((s) => s.value);

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

  if (!socket.connected) socket.connect();
  socket.emit("scan", {
    platforms: [props.platform.id],
    type: scanType.value,
    apis,
    launchbox_remote_enabled: launchboxRemoteEnabled.value,
    playmatch_enabled: playmatchMatcher
      ? isHashMatcherOn(playmatchMatcher)
      : false,
  });

  snackbar.info(`Scanning ${props.platform.display_name}…`, {
    icon: "mdi-loading mdi-spin",
  });
  closeDialog();
}
</script>

<template>
  <RDialog
    :model-value="modelValue"
    icon="mdi-magnify-scan"
    :width="560"
    @update:model-value="$emit('update:modelValue', $event)"
    @close="closeDialog"
  >
    <template #header>
      <span>{{ t("scan.scan", "Scan platform") }}</span>
    </template>

    <template #content>
      <div class="r-v2-scan-plat">
        <!-- Platform identity row — icon + name. Mirrors the
             ROM-identity row in RefreshMetadataDialog so the two
             scan-launching surfaces read as siblings. -->
        <div class="r-v2-scan-plat__head">
          <div class="r-v2-scan-plat__icon">
            <RPlatformIcon
              :slug="platform.slug"
              :fs-slug="platform.fs_slug"
              :alt="platform.display_name"
              :size="40"
            />
          </div>
          <div class="r-v2-scan-plat__meta">
            <p class="r-v2-scan-plat__name" :title="platform.display_name">
              {{ platform.display_name }}
            </p>
            <p class="r-v2-scan-plat__rom-count">
              {{ t("platform.rom-count", { n: platform.rom_count ?? 0 }) }}
            </p>
          </div>
        </div>

        <!-- 1. Providers — General + Specific RSelects. -->
        <section class="r-v2-scan-plat__section">
          <h3 class="r-v2-scan-plat__section-title">
            {{ t("scan.section-providers") }}
          </h3>

          <div class="r-v2-scan-plat__providers-group">
            <span class="r-v2-scan-plat__providers-group-label">
              {{ t("scan.section-providers-general") }}
            </span>
            <RSelect
              v-model="metadataSources"
              :items="generalProviders"
              :label="t('scan.section-providers-general')"
              item-title="name"
              prepend-inner-icon="mdi-database-search"
              variant="outlined"
              density="comfortable"
              multiple
              return-object
              clearable
              hide-details
              chips
              chip-tone="plain"
              show-all-option
            >
              <template #chip="{ item }">
                <RTooltip :text="item.raw.name" location="bottom">
                  <template #activator="{ props: tipProps }">
                    <span
                      v-bind="tipProps"
                      class="r-v2-scan-plat__provider-chip"
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
                  <RAvatar :image="item.raw.logo_path" size="22" rounded="sm" />
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

                  <div
                    v-if="item.raw.value === 'launchbox'"
                    class="r-v2-scan-plat__lb-toggle"
                    @click.stop
                    @mousedown.stop
                  >
                    <span
                      class="r-v2-scan-plat__lb-label"
                      :class="{
                        'r-v2-scan-plat__lb-inactive': launchboxRemoteEnabled,
                      }"
                    >
                      Local
                    </span>
                    <RSwitch
                      v-model="launchboxRemoteEnabled"
                      :disabled="!isLaunchboxSelected"
                    />
                    <span
                      class="r-v2-scan-plat__lb-label"
                      :class="{
                        'r-v2-scan-plat__lb-inactive': !launchboxRemoteEnabled,
                      }"
                    >
                      Cloud
                    </span>
                  </div>
                </li>
              </template>
            </RSelect>
          </div>

          <div
            v-if="specificProviders.length"
            class="r-v2-scan-plat__providers-group"
          >
            <span class="r-v2-scan-plat__providers-group-label">
              {{ t("scan.section-providers-specific") }}
            </span>
            <RSelect
              v-model="metadataSources"
              :items="specificProviders"
              :label="t('scan.section-providers-specific')"
              item-title="name"
              prepend-inner-icon="mdi-trophy-outline"
              variant="outlined"
              density="comfortable"
              multiple
              return-object
              clearable
              hide-details
              chips
              chip-tone="plain"
              show-all-option
            >
              <template #chip="{ item }">
                <RTooltip :text="item.raw.name" location="bottom">
                  <template #activator="{ props: tipProps }">
                    <span
                      v-bind="tipProps"
                      class="r-v2-scan-plat__provider-chip"
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
                  <RAvatar :image="item.raw.logo_path" size="22" rounded="sm" />
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
        </section>

        <!-- 2. Hash-matcher proxies — same compact switch pills as
             RefreshMetadataDialog. -->
        <section class="r-v2-scan-plat__section">
          <h3 class="r-v2-scan-plat__section-title">
            {{ t("scan.section-proxies") }}
          </h3>
          <div
            class="r-v2-scan-plat__matchers"
            role="group"
            aria-label="Hash matchers"
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
                  class="r-v2-scan-plat__matcher"
                  :class="{
                    'r-v2-scan-plat__matcher--off': !matcher.switchEnabled,
                  }"
                >
                  <RAvatar
                    :image="matcher.logo"
                    size="16"
                    rounded="sm"
                    class="r-v2-scan-plat__matcher-logo"
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
        </section>

        <!-- 3. Scan type — full per-platform option list (no "new
             platforms" — that's a library-wide discovery scan). -->
        <section class="r-v2-scan-plat__section">
          <h3 class="r-v2-scan-plat__section-title">
            {{ t("scan.section-scan-type") }}
          </h3>
          <RSelect
            v-model="scanType"
            :items="scanOptions"
            :label="t('scan.scan-options')"
            prepend-inner-icon="mdi-magnify-scan"
            hide-details
            variant="outlined"
            density="comfortable"
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
        </section>

        <RAlert
          v-if="!calculateHashes"
          type="warning"
          density="compact"
          :icon="false"
          class="r-v2-scan-plat__hint"
        >
          {{ t("scan.hash-calculation-disabled") }}
        </RAlert>
      </div>
    </template>

    <template #footer>
      <RBtn variant="text" @click="closeDialog">
        {{ t("common.cancel") }}
      </RBtn>
      <span class="r-v2-scan-plat__footer-spacer" />
      <RBtn
        variant="translucent"
        color="primary"
        prepend-icon="mdi-magnify-scan"
        :disabled="metadataSources.length === 0"
        @click="onScan"
      >
        {{ t("scan.scan", "Scan") }}
      </RBtn>
    </template>
  </RDialog>
</template>

<style scoped>
.r-v2-scan-plat {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.r-v2-scan-plat__footer-spacer {
  flex: 1;
}

/* Platform identity row — sibling of `.r-v2-refresh__rom` in
   RefreshMetadataDialog. */
.r-v2-scan-plat__head {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  background: var(--r-color-bg-elevated);
  border: 1px solid var(--r-color-border);
  border-radius: var(--r-radius-md);
}
.r-v2-scan-plat__icon {
  width: 40px;
  height: 40px;
  flex-shrink: 0;
  display: grid;
  place-items: center;
}
.r-v2-scan-plat__meta {
  min-width: 0;
  flex: 1;
}
.r-v2-scan-plat__name {
  margin: 0;
  font-size: 13px;
  font-weight: var(--r-font-weight-semibold);
  color: var(--r-color-fg);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.r-v2-scan-plat__rom-count {
  margin: 2px 0 0;
  font-size: 11px;
  color: var(--r-color-fg-muted);
  font-variant-numeric: tabular-nums;
}

.r-v2-scan-plat__section {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding-top: 12px;
  border-top: 1px solid var(--r-color-border);
}
.r-v2-scan-plat__section:first-of-type {
  padding-top: 0;
  border-top: 0;
}
.r-v2-scan-plat__section-title {
  margin: 0;
  font-size: 11px;
  font-weight: var(--r-font-weight-semibold);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--r-color-fg-muted);
}

.r-v2-scan-plat__providers-group {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.r-v2-scan-plat__providers-group + .r-v2-scan-plat__providers-group {
  margin-top: 8px;
}
.r-v2-scan-plat__providers-group-label {
  font-size: 10px;
  font-weight: var(--r-font-weight-medium);
  letter-spacing: 0.04em;
  color: var(--r-color-fg-faint);
}

.r-v2-scan-plat__provider-chip {
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.r-v2-scan-plat__matchers {
  display: flex;
  flex-direction: row;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  align-self: flex-start;
}
.r-v2-scan-plat__matcher {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 8px;
  border-radius: var(--r-radius-pill);
  background: var(--r-color-surface);
  border: 1px solid var(--r-color-border);
}
.r-v2-scan-plat__matcher--off {
  opacity: 0.55;
}
.r-v2-scan-plat__matcher-logo {
  background: var(--r-color-bg-elevated);
  flex-shrink: 0;
}

.r-v2-scan-plat__lb-toggle {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-left: auto;
}
.r-v2-scan-plat__lb-label {
  font-size: 11px;
  color: var(--r-color-fg);
  white-space: nowrap;
}
.r-v2-scan-plat__lb-inactive {
  color: var(--r-color-fg-muted);
}

.r-v2-scan-plat__hint {
  margin-top: -4px;
}
</style>
