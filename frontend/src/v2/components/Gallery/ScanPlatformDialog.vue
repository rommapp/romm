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
import { RAlert, RBtn, RDialog } from "@v2/lib";
import { computed, ref } from "vue";
import { useI18n } from "vue-i18n";
import type { Platform } from "@/stores/platforms";
import ScanHashMatcherSwitches from "@/v2/components/Scan/ScanHashMatcherSwitches.vue";
import ScanProviderSelect from "@/v2/components/Scan/ScanProviderSelect.vue";
import ScanTypeSelect from "@/v2/components/Scan/ScanTypeSelect.vue";
import PlatformIcon from "@/v2/components/shared/PlatformIcon.vue";
import { useScanProviders } from "@/v2/composables/useScanProviders";
import { useScanTrigger } from "@/v2/composables/useScanTrigger";
import { useScanTypeOptions } from "@/v2/composables/useScanTypeOptions";
import { useSnackbar } from "@/v2/composables/useSnackbar";
import {
  type ScanType as SharedScanType,
  type ScanTypeOption,
} from "@/v2/types/scan";

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

const allScanOptions = useScanTypeOptions();
const scanOptions = computed(() =>
  allScanOptions.value.filter(
    (o): o is ScanTypeOption<ScanType> => o.value !== "new_platforms",
  ),
);
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
          <h3 class="r-v2-scan-plat__section-title">
            {{ t("scan.section-providers") }}
          </h3>

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

        <!-- 2. Hash-matcher proxies. -->
        <section class="r-v2-scan-plat__section">
          <h3 class="r-v2-scan-plat__section-title">
            {{ t("scan.section-proxies") }}
          </h3>
          <ScanHashMatcherSwitches
            :matchers="hashMatchers"
            :is-on="isHashMatcherOn"
            @toggle="setHashMatcher"
          />
        </section>

        <!-- 3. Scan type, full per-platform option list (no "new
             platforms", that's a library-wide discovery scan). -->
        <section class="r-v2-scan-plat__section">
          <h3 class="r-v2-scan-plat__section-title">
            {{ t("scan.section-scan-type") }}
          </h3>
          <ScanTypeSelect v-model="scanType" :items="scanOptions" />
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
.r-v2-scan-plat__section-title {
  margin: 0;
  font-size: 11px;
  font-weight: var(--r-font-weight-semibold);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--r-color-fg-muted);
}

.r-v2-scan-plat__hint {
  margin-top: -4px;
}
</style>
