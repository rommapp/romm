<script setup lang="ts">
// RefreshMetadataDialog — kicks off a per-ROM (or bulk) metadata
// re-scan. Shares the visual vocabulary of the Scan view config card:
// provider selects split into General / Specific, hash-matcher proxies
// rendered as switch pills, and a scan-type select with two per-ROM-
// friendly options. Emits the same `scan` socket event as the main Scan
// view (lifecycle handlers live globally in AppLayout).
import {
  RAvatar,
  RAlert,
  RBtn,
  RDialog,
  RIcon,
  RSelect,
  RSwitch,
  RTooltip,
} from "@v2/lib";
import type { Emitter } from "mitt";
import { computed, inject, onBeforeUnmount, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import { type SimpleRom } from "@/stores/roms";
import type { Events } from "@/types/emitter";
import { useScanProviders } from "@/v2/composables/useScanProviders";
import { useScanTrigger } from "@/v2/composables/useScanTrigger";
import { useSnackbar } from "@/v2/composables/useSnackbar";
import {
  scanNeedsMetadataSource,
  type ScanType as SharedScanType,
} from "@/v2/types/scan";

defineOptions({ inheritAttrs: false });

const { t } = useI18n();
const emitter = inject<Emitter<Events>>("emitter");
const snackbar = useSnackbar();
const show = ref(false);
// Accept either a single rom or an array — the SelectionBar passes
// many at once, individual menus pass one. Internally we always
// normalise to an array so the scan emit groups by platform without
// branching on the input shape.
const roms = ref<SimpleRom[]>([]);
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
  buildScanPayload,
  persistSelection,
} = useScanProviders();

// Per-ROM scan types. "new platforms" means nothing here and "unmatched" is a
// library-wide filter; "quick" is offered as "Refresh files", which is all a
// quick scan does for a ROM that already exists.
type ScanType = Extract<
  SharedScanType,
  "update" | "hashes" | "quick" | "complete"
>;

const isBulk = computed(() => roms.value.length > 1);

interface ScanOption {
  title: string;
  subtitle: string;
  value: ScanType;
  disabled?: string;
}

const scanOptions = computed<ScanOption[]>(() => [
  {
    title: t("scan.update-metadata"),
    subtitle: isBulk.value
      ? t("rom.refresh-update-desc-bulk")
      : t("rom.refresh-update-desc"),
    value: "update",
  },
  {
    title: t("scan.hashes"),
    subtitle: isBulk.value
      ? t("rom.refresh-hashes-desc-bulk")
      : t("rom.refresh-hashes-desc"),
    value: "hashes",
    disabled: calculateHashes.value
      ? undefined
      : t("scan.hash-calculation-disabled"),
  },
  {
    title: t("rom.refresh-files"),
    subtitle: isBulk.value
      ? t("rom.refresh-files-desc-bulk")
      : t("rom.refresh-files-desc"),
    value: "quick",
  },
  {
    title: t("scan.complete-rescan"),
    subtitle: t("rom.refresh-complete-desc"),
    value: "complete",
  },
]);
const scanType = ref<ScanType>("update");

// Reset scan type back to the safe default if the current selection
// becomes disabled (e.g. user toggles SKIP_HASH_CALCULATION while the
// dialog is open and `hashes` was selected).
watch(scanOptions, (options) => {
  const current = options.find((o) => o.value === scanType.value);
  if (current?.disabled) scanType.value = "update";
});

const openSingle = (payload: SimpleRom) => {
  roms.value = [payload];
  show.value = true;
};
const openBulk = (payload: SimpleRom[]) => {
  roms.value = payload;
  show.value = true;
};
emitter?.on("showRefreshMetadataDialog", openSingle);
emitter?.on("showRefreshMetadataDialogBulk", openBulk);
onBeforeUnmount(() => {
  emitter?.off("showRefreshMetadataDialog", openSingle);
  emitter?.off("showRefreshMetadataDialogBulk", openBulk);
});

const singleRom = computed<SimpleRom | null>(() =>
  roms.value.length === 1 ? roms.value[0] : null,
);
const singleRomCover = computed<string | null>(() => {
  const r = singleRom.value;
  if (!r) return null;
  return r.path_cover_small ?? r.url_cover ?? null;
});
const singleRomTitle = computed(() => {
  const r = singleRom.value;
  return r ? (r.name ?? r.fs_name) : "";
});

function onScan() {
  if (roms.value.length === 0) return;

  // Group rom ids by platform — the scan socket event accepts one
  // platform list + one rom-id list, so a selection that spans
  // multiple platforms is fanned into N events, one per platform.
  const byPlatform = new Map<number, number[]>();
  for (const r of roms.value) {
    const list = byPlatform.get(r.platform_id) ?? [];
    list.push(r.id);
    byPlatform.set(r.platform_id, list);
  }

  const payload = buildScanPayload();
  const started = startScan(
    [...byPlatform].map(([platformId, romIds]) => ({
      platforms: [platformId],
      roms_ids: romIds,
      type: scanType.value,
      ...payload,
    })),
  );
  if (!started) return;
  persistSelection();

  if (isBulk.value) {
    snackbar.info(t("rom.refresh-metadata-bulk", { n: roms.value.length }), {
      icon: "mdi-loading mdi-spin",
    });
  } else {
    const name = singleRomTitle.value;
    snackbar.info(
      scanType.value === "quick"
        ? t("rom.refreshing-files", { name })
        : t("rom.refreshing-metadata", { name }),
      { icon: "mdi-loading mdi-spin" },
    );
  }

  closeDialog();
}

function closeDialog() {
  show.value = false;
  roms.value = [];
}
</script>

<template>
  <RDialog
    v-model="show"
    icon="mdi-magnify-scan"
    width="560"
    @close="closeDialog"
  >
    <template #header>
      <span>{{ t("rom.refresh-metadata") }}</span>
    </template>
    <template #content>
      <div class="r-v2-refresh">
        <!-- ROM identity row — cover + name for the single-ROM case
             (visual consistency with EditRomDialog / DeleteRomDialog),
             count chip for bulk. -->
        <div v-if="singleRom" class="r-v2-refresh__rom">
          <div class="r-v2-refresh__cover">
            <img
              v-if="singleRomCover"
              :src="singleRomCover"
              :alt="singleRomTitle"
            />
            <div v-else class="r-v2-refresh__cover-placeholder">
              <RIcon icon="mdi-disc" size="20" />
            </div>
          </div>
          <div class="r-v2-refresh__meta">
            <p class="r-v2-refresh__name" :title="singleRomTitle">
              {{ singleRomTitle }}
            </p>
            <p
              v-if="singleRom.fs_name"
              class="r-v2-refresh__filename"
              :title="singleRom.fs_name"
            >
              {{ singleRom.fs_name }}
            </p>
          </div>
        </div>
        <div v-else-if="isBulk" class="r-v2-refresh__rom-bulk">
          <RIcon icon="mdi-disc-player" size="18" />
          <span>{{ t("rom.selection-count", { n: roms.length }) }}</span>
        </div>

        <!-- 1. Providers section — General + Specific RSelects, sharing
             one `metadataSources` model. Both render icon-only chips so
             a multi-select stays visually quiet in the activator. -->
        <section class="r-v2-refresh__section">
          <h3 class="r-v2-refresh__section-title">
            {{ t("scan.section-providers") }}
          </h3>

          <div class="r-v2-refresh__providers-group">
            <span class="r-v2-refresh__providers-group-label">
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
              @update:all-selected="generalAllSelected = $event"
            >
              <template #chip="{ item }">
                <RTooltip :text="item.raw.name" location="bottom">
                  <template #activator="{ props: tipProps }">
                    <span
                      v-bind="tipProps"
                      class="r-v2-refresh__provider-chip"
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

                  <!-- LaunchBox Local/Cloud toggle — inline inside its
                       dropdown row, disabled until LaunchBox itself is
                       selected. Same pattern as Scan.vue. -->
                  <div
                    v-if="item.raw.value === 'launchbox'"
                    class="r-v2-refresh__lb-toggle"
                    @click.stop
                    @mousedown.stop
                  >
                    <span
                      class="r-v2-refresh__lb-label"
                      :class="{
                        'r-v2-refresh__lb-inactive': launchboxRemoteEnabled,
                      }"
                    >
                      {{ t("rom.launchbox-local") }}
                    </span>
                    <RSwitch
                      v-model="launchboxRemoteEnabled"
                      :disabled="!isLaunchboxSelected"
                    />
                    <span
                      class="r-v2-refresh__lb-label"
                      :class="{
                        'r-v2-refresh__lb-inactive': !launchboxRemoteEnabled,
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
            class="r-v2-refresh__providers-group"
          >
            <span class="r-v2-refresh__providers-group-label">
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
              @update:all-selected="specificAllSelected = $event"
            >
              <template #chip="{ item }">
                <RTooltip :text="item.raw.name" location="bottom">
                  <template #activator="{ props: tipProps }">
                    <span
                      v-bind="tipProps"
                      class="r-v2-refresh__provider-chip"
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

        <!-- 2. Proxies (hash matchers) — compact switch pills, same as
             the Scan view. -->
        <section class="r-v2-refresh__section">
          <h3 class="r-v2-refresh__section-title">
            {{ t("scan.section-proxies") }}
          </h3>
          <div
            class="r-v2-refresh__matchers"
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
                  class="r-v2-refresh__matcher"
                  :class="{
                    'r-v2-refresh__matcher--off': !matcher.switchEnabled,
                  }"
                >
                  <RAvatar
                    :image="matcher.logo"
                    size="16"
                    rounded="sm"
                    class="r-v2-refresh__matcher-logo"
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

        <!-- 3. Scan type — per-ROM friendly options. -->
        <section class="r-v2-refresh__section">
          <h3 class="r-v2-refresh__section-title">
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
                  <div
                    v-if="item.raw.disabled || item.raw.subtitle"
                    class="r-select__item-subtitle"
                  >
                    {{ item.raw.disabled || item.raw.subtitle }}
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
          class="r-v2-refresh__hint"
        >
          {{ t("scan.hash-calculation-disabled") }}
        </RAlert>
      </div>
    </template>
    <template #footer>
      <RBtn variant="text" @click="closeDialog">
        {{ t("common.cancel") }}
      </RBtn>
      <div style="flex: 1" />
      <RBtn
        variant="translucent"
        color="primary"
        prepend-icon="mdi-magnify-scan"
        :disabled="
          effectiveMetadataSources.length === 0 &&
          scanNeedsMetadataSource(scanType)
        "
        @click="onScan"
      >
        {{ t("rom.refresh-metadata") }}
      </RBtn>
    </template>
  </RDialog>
</template>

<style scoped>
.r-v2-refresh {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* ROM identity row — cover + name + filename. Mirrors the row layout
   in DeleteRomDialog so the two "do-something-with-this-ROM" dialogs
   read as siblings. */
.r-v2-refresh__rom {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  background: var(--r-color-bg-elevated);
  border: 1px solid var(--r-color-border);
  border-radius: var(--r-radius-md);
}
.r-v2-refresh__cover {
  width: 40px;
  aspect-ratio: 3 / 4;
  flex-shrink: 0;
  border-radius: var(--r-radius-sm);
  overflow: hidden;
  background: var(--r-color-cover-placeholder);
  display: grid;
  place-items: center;
}
.r-v2-refresh__cover img {
  width: 100%;
  height: 100%;
  /* Whole cover at its natural aspect (no crop); the slot stays uniform. */
  object-fit: contain;
  display: block;
}
.r-v2-refresh__cover-placeholder {
  color: var(--r-color-fg-faint);
}
.r-v2-refresh__meta {
  min-width: 0;
  flex: 1;
}
.r-v2-refresh__name {
  margin: 0;
  font-size: 13px;
  font-weight: var(--r-font-weight-semibold);
  color: var(--r-color-fg);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.r-v2-refresh__filename {
  margin: 2px 0 0;
  font-size: 11px;
  font-family: var(--r-font-family-mono, monospace);
  color: var(--r-color-brand-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.r-v2-refresh__rom-bulk {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: var(--r-color-bg-elevated);
  border: 1px solid var(--r-color-border);
  border-radius: var(--r-radius-md);
  font-size: 13px;
  font-weight: var(--r-font-weight-semibold);
  color: var(--r-color-fg);
  align-self: flex-start;
}

/* Section vocabulary — small uppercase label above the controls,
   hairline divider between sections. Same rhythm as Scan.vue. */
.r-v2-refresh__section {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding-top: 12px;
  border-top: 1px solid var(--r-color-border);
}
.r-v2-refresh__section:first-of-type {
  padding-top: 0;
  border-top: 0;
}
.r-v2-refresh__section-title {
  margin: 0;
  font-size: 11px;
  font-weight: var(--r-font-weight-semibold);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--r-color-fg-muted);
}

/* Provider groups (General / Specific) — same layout as Scan.vue: a
   small caption above each RSelect, two groups stacked with a tight
   inter-group margin. */
.r-v2-refresh__providers-group {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.r-v2-refresh__providers-group + .r-v2-refresh__providers-group {
  margin-top: 8px;
}
.r-v2-refresh__providers-group-label {
  font-size: 10px;
  font-weight: var(--r-font-weight-medium);
  letter-spacing: 0.04em;
  color: var(--r-color-fg-faint);
}

/* Icon-only chip rendered in the activator — keeps the multi-select
   visually quiet when many providers are picked. */
.r-v2-refresh__provider-chip {
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

/* Hash matcher pills — same compact icon + switch rows as Scan.vue. */
.r-v2-refresh__matchers {
  display: flex;
  flex-direction: row;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  align-self: flex-start;
}
.r-v2-refresh__matcher {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 8px;
  border-radius: var(--r-radius-pill);
  background: var(--r-color-surface);
  border: 1px solid var(--r-color-border);
}
.r-v2-refresh__matcher--off {
  opacity: 0.55;
}
.r-v2-refresh__matcher-logo {
  background: var(--r-color-bg-elevated);
  flex-shrink: 0;
}

/* LaunchBox Local/Cloud inline toggle inside its dropdown row. */
.r-v2-refresh__lb-toggle {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-left: auto;
}
.r-v2-refresh__lb-label {
  font-size: 11px;
  color: var(--r-color-fg);
  white-space: nowrap;
}
.r-v2-refresh__lb-inactive {
  color: var(--r-color-fg-muted);
}

.r-v2-refresh__hint {
  margin-top: -4px;
}
</style>
