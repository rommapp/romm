<script setup lang="ts">
// ScanPlatformDialog: kicks off a scan for a single platform with
// the user's choice of providers, hash-matchers, and scan type.
//
// Visual + interaction language mirrors `RefreshMetadataDialog`
// (provider selects split into General / Specific, hash-matcher
// proxies as switch pills, scan-type select), but the identity row
// at the top shows the platform instead of a ROM, and the scan-type
// list mirrors the Scan view's per-platform options (no "new
// platforms": that's a discovery scan against the whole library,
// not a single platform).
import {
  RAlert,
  RAvatar,
  RBtn,
  RDialog,
  RSectionLabel,
  RSelect,
  RSwitch,
  RTooltip,
} from "@v2/lib";
import { computed, ref } from "vue";
import { useI18n } from "vue-i18n";
import type { Platform } from "@/stores/platforms";
import ScanProviderSelect from "@/v2/components/Scan/ScanProviderSelect.vue";
import PlatformIcon from "@/v2/components/shared/PlatformIcon.vue";
import { useScanProviders } from "@/v2/composables/useScanProviders";
import { useScanTrigger } from "@/v2/composables/useScanTrigger";
import { useSnackbar } from "@/v2/composables/useSnackbar";
import { type ScanType as SharedScanType } from "@/v2/types/scan";

defineOptions({ inheritAttrs: false });

const props = defineProps<{
  modelValue: boolean;
  platform: Platform;
}>();

const emit = defineEmits<{
  (e: "update:modelValue", v: boolean): void;
}>();

const { t } = useI18n();
const snackbar = useSnackbar();
const { startScan } = useScanTrigger();

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
  buildScanSourceOptions,
  persistSelection,
} = useScanProviders();

// Per-platform scan types: the full Scan-view list minus
// `new_platforms` (a discovery scan against fs_slugs not yet in the
// DB, which can't be scoped to a known platform).
type ScanType = Exclude<SharedScanType, "new_platforms">;

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
  const started = startScan([
    {
      platforms: [props.platform.id],
      type: scanType.value,
      ...buildScanSourceOptions(),
    },
  ]);
  if (!started) return;
  persistSelection();

  snackbar.info(
    t("scan.scanning-platform", { platform: props.platform.display_name }),
    {
      icon: "mdi-loading mdi-spin",
    },
  );
  closeDialog();
}
</script>

<template>
  <RDialog
    :model-value="modelValue"
    icon="mdi-magnify-scan"
    :width="560"
    cancelable
    @update:model-value="$emit('update:modelValue', $event)"
    @close="closeDialog"
  >
    <template #header>
      <span>{{ t("scan.scan", "Scan platform") }}</span>
    </template>

    <template #content>
      <div class="r-v2-scan-plat">
        <!-- Platform identity row: icon + name. Mirrors the
             ROM-identity row in RefreshMetadataDialog so the two
             scan-launching surfaces read as siblings. -->
        <div class="r-v2-scan-plat__head">
          <div class="r-v2-scan-plat__icon">
            <PlatformIcon
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

        <!-- 1. Providers: General + Specific RSelects. -->
        <section class="r-v2-scan-plat__section">
          <RSectionLabel as="h3">
            {{ t("scan.section-providers") }}
          </RSectionLabel>

          <ScanProviderSelect
            v-model="metadataSources"
            v-model:launchbox-remote="launchboxRemoteEnabled"
            :items="generalProviders"
            :label="t('scan.section-providers-general')"
            icon="mdi-database-search"
            :launchbox-selected="isLaunchboxSelected"
            @update:all-selected="generalAllSelected = $event"
          />
          <ScanProviderSelect
            v-if="specificProviders.length"
            v-model="metadataSources"
            :items="specificProviders"
            :label="t('scan.section-providers-specific')"
            icon="mdi-trophy-outline"
            @update:all-selected="specificAllSelected = $event"
          />
        </section>

        <!-- 2. Hash-matcher proxies: same compact switch pills as
             RefreshMetadataDialog. -->
        <section class="r-v2-scan-plat__section">
          <RSectionLabel as="h3">
            {{ t("scan.section-proxies") }}
          </RSectionLabel>
          <div
            class="r-v2-scan-plat__matchers"
            role="group"
            :aria-label="t('rom.hash-matchers')"
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

        <!-- 3. Scan type, full per-platform option list (no "new
             platforms", that's a library-wide discovery scan). -->
        <section class="r-v2-scan-plat__section">
          <RSectionLabel as="h3">
            {{ t("scan.section-scan-type") }}
          </RSectionLabel>
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
      <RBtn
        variant="translucent"
        color="primary"
        prepend-icon="mdi-magnify-scan"
        :disabled="
          effectiveMetadataSources.length === 0 && scanType !== 'quick'
        "
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

/* Platform identity row: sibling of `.r-v2-refresh__rom` in
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

.r-v2-scan-plat__hint {
  margin-top: -4px;
}
</style>
