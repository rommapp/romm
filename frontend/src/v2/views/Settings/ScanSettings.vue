<script setup lang="ts">
// ScanSettings — v2-native editor for the scan.* section of config.yml
// (metadata/artwork priority, region & language priority, media types,
// gamelist/pegasus export). Persists via PUT /config/scan.
//
// Provider / region / language identifiers are proper nouns or codes, so
// they stay as data constants; only descriptive prose goes through i18n.
import {
  RAlert,
  RComboboxField,
  RIcon,
  RSelect,
  RBtn,
  RSpinner,
} from "@v2/lib";
import { storeToRefs } from "pinia";
import { computed, onBeforeUnmount, onMounted, reactive, ref } from "vue";
import { useI18n } from "vue-i18n";
import { onBeforeRouteLeave } from "vue-router";
import type { MetadataMediaType, ScanSettingsPayload } from "@/__generated__";
import configApi from "@/services/api/config";
import storeAuth from "@/stores/auth";
import storeConfig, { type Config } from "@/stores/config";
import ScanPriorityList from "@/v2/components/Settings/ScanPriorityList.vue";
import SettingsSection from "@/v2/components/Settings/SettingsSection.vue";
import SettingsSubsection from "@/v2/components/Settings/SettingsSubsection.vue";
import SettingsToggleRow from "@/v2/components/Settings/SettingsToggleRow.vue";
import { useConfirm } from "@/v2/composables/useConfirm";
import { useSnackbar } from "@/v2/composables/useSnackbar";

const { t } = useI18n();
const confirm = useConfirm();
const configStore = storeConfig();
const { config } = storeToRefs(configStore);
const authStore = storeAuth();
const snackbar = useSnackbar();

// Provider brand names — identical across every locale, so not i18n'd.
const PROVIDER_LABELS: Record<string, string> = {
  igdb: "IGDB",
  moby: "MobyGames",
  ss: "ScreenScraper",
  ra: "RetroAchievements",
  launchbox: "LaunchBox",
  hasheous: "Hasheous",
  tgdb: "TheGamesDB",
  sgdb: "SteamGridDB",
  flashpoint: "Flashpoint",
  hltb: "HowLongToBeat",
  gamelist: "ES-DE gamelist",
  libretro: "Libretro",
  playmatch: "Playmatch",
};
const METADATA_SOURCES = [
  "igdb",
  "moby",
  "ss",
  "ra",
  "launchbox",
  "gamelist",
  "hasheous",
  "tgdb",
  "flashpoint",
  "hltb",
  "sgdb",
  "libretro",
  "playmatch",
].map((value) => ({ value, label: PROVIDER_LABELS[value] }));
const ARTWORK_SOURCES = [
  "sgdb",
  "igdb",
  "moby",
  "ss",
  "libretro",
  "ra",
  "launchbox",
  "gamelist",
  "hasheous",
  "tgdb",
  "flashpoint",
  "hltb",
  "playmatch",
].map((value) => ({ value, label: PROVIDER_LABELS[value] }));

// Common provider region / language codes, offered as autocomplete
// suggestions. Users may still type any provider-defined code.
const REGION_SUGGESTIONS = [
  "us",
  "wor",
  "ss",
  "eu",
  "jp",
  "uk",
  "fr",
  "de",
  "it",
  "sp",
  "br",
  "ca",
  "au",
  "kr",
  "cn",
  "tw",
  "hk",
  "ru",
  "nl",
  "se",
  "no",
  "fi",
];
const LANGUAGE_SUGGESTIONS = [
  "en",
  "fr",
  "de",
  "es",
  "it",
  "pt",
  "nl",
  "ja",
  "ko",
  "zh",
  "ru",
  "pl",
  "sv",
  "da",
  "no",
  "fi",
  "ar",
  "el",
];

const MEDIA_TYPES: MetadataMediaType[] = [
  "box2d",
  "box3d",
  "box2d_back",
  "box2d_side",
  "miximage",
  "miximage_v2",
  "physical",
  "screenshot",
  "title_screen",
  "fanart",
  "marquee",
  "logo",
  "bezel",
  "manual",
  "video",
  "video_normalized",
];
const THUMBNAIL_TYPES: MetadataMediaType[] = [
  "box2d",
  "box3d",
  "miximage",
  "miximage_v2",
  "physical",
];
const IMAGE_TYPES: MetadataMediaType[] = [
  "title_screen",
  "miximage",
  "miximage_v2",
  "box2d",
  "screenshot",
];

const mediaLabel = (value: string) =>
  t(`settings.media-${value.replaceAll("_", "-")}`);

const mediaItems = computed(() =>
  MEDIA_TYPES.map((value) => ({ title: mediaLabel(value), value })),
);
const thumbnailItems = computed(() =>
  THUMBNAIL_TYPES.map((value) => ({ title: mediaLabel(value), value })),
);
const imageItems = computed(() =>
  IMAGE_TYPES.map((value) => ({ title: mediaLabel(value), value })),
);

// ── Editable form model ────────────────────────────────────────────
interface ScanForm {
  metadata: string[];
  artwork: string[];
  coverEnabled: boolean;
  cover: string[];
  screenshotEnabled: boolean;
  screenshot: string[];
  manualEnabled: boolean;
  manual: string[];
  region: string[];
  language: string[];
  media: string[];
  gamelistExport: boolean;
  gamelistThumbnail: MetadataMediaType;
  gamelistImage: MetadataMediaType;
  pegasusExport: boolean;
}

function configToForm(cfg: Config): ScanForm {
  const overrides = cfg.SCAN_ARTWORK_PRIORITY_OVERRIDES ?? {};
  return {
    metadata: [...(cfg.SCAN_METADATA_PRIORITY ?? [])],
    artwork: [...(cfg.SCAN_ARTWORK_PRIORITY ?? [])],
    coverEnabled: "url_cover" in overrides,
    cover: [...(overrides.url_cover ?? cfg.SCAN_ARTWORK_PRIORITY ?? [])],
    screenshotEnabled: "url_screenshots" in overrides,
    screenshot: [
      ...(overrides.url_screenshots ?? cfg.SCAN_ARTWORK_PRIORITY ?? []),
    ],
    manualEnabled: "url_manual" in overrides,
    manual: [...(overrides.url_manual ?? cfg.SCAN_ARTWORK_PRIORITY ?? [])],
    region: [...(cfg.SCAN_REGION_PRIORITY ?? [])],
    language: [...(cfg.SCAN_LANGUAGE_PRIORITY ?? [])],
    media: [...(cfg.SCAN_MEDIA ?? [])],
    gamelistExport: cfg.GAMELIST_AUTO_EXPORT_ON_SCAN ?? false,
    gamelistThumbnail: (cfg.GAMELIST_MEDIA_THUMBNAIL ??
      "box2d") as MetadataMediaType,
    gamelistImage: (cfg.GAMELIST_MEDIA_IMAGE ??
      "screenshot") as MetadataMediaType,
    pegasusExport: cfg.PEGASUS_AUTO_EXPORT_ON_SCAN ?? false,
  };
}

function formToPayload(f: ScanForm): ScanSettingsPayload {
  return {
    metadata_priority: f.metadata,
    artwork_priority: f.artwork,
    cover_priority: f.coverEnabled ? f.cover : null,
    screenshot_priority: f.screenshotEnabled ? f.screenshot : null,
    manual_priority: f.manualEnabled ? f.manual : null,
    region_priority: f.region,
    language_priority: f.language,
    media: f.media as MetadataMediaType[],
    gamelist_export: f.gamelistExport,
    gamelist_thumbnail: f.gamelistThumbnail,
    gamelist_image: f.gamelistImage,
    pegasus_export: f.pegasusExport,
  };
}

const form = reactive<ScanForm>(configToForm(config.value));
// Snapshot of the last-saved payload, for dirty detection.
const savedSnapshot = ref(JSON.stringify(formToPayload(form)));

function resetForm(cfg: Config) {
  Object.assign(form, configToForm(cfg));
  savedSnapshot.value = JSON.stringify(formToPayload(form));
}

const dirty = computed(
  () => JSON.stringify(formToPayload(form)) !== savedSnapshot.value,
);

const canEdit = computed(
  () =>
    authStore.scopes.includes("platforms.write") &&
    config.value.CONFIG_FILE_WRITABLE,
);

const loading = ref(true);
const loadError = ref(false);
const saving = ref(false);

async function loadConfig() {
  loading.value = true;
  loadError.value = false;
  try {
    resetForm(await configStore.fetchConfig({ rethrow: true }));
  } catch {
    loadError.value = true;
  } finally {
    loading.value = false;
  }
}

onMounted(loadConfig);

function onReset() {
  resetForm(config.value);
}

async function onSave() {
  saving.value = true;
  try {
    const payload = formToPayload(form);
    await configApi.updateScanSettings(payload);
    savedSnapshot.value = JSON.stringify(payload);
    await configStore.fetchConfig();
    snackbar.success(t("settings.scan-settings-saved"));
  } catch (err) {
    const e = err as {
      response?: { data?: { detail?: string }; statusText?: string };
      message?: string;
    };
    const detail =
      e?.response?.data?.detail || e?.response?.statusText || e?.message;
    snackbar.error(t("settings.scan-settings-save-error", { detail }));
  } finally {
    saving.value = false;
  }
}

function setMedia(value: unknown) {
  form.media = (value as string[]) ?? [];
}

// ── Unsaved-changes guard ───────────────────────────────────────────
// Block navigating away with pending edits until the user saves,
// discards, or explicitly confirms leaving. Two layers: an in-app route
// guard for SPA navigation, and `beforeunload` for tab close / reload /
// external links.
const hasPendingEdits = () => dirty.value && canEdit.value;

onBeforeRouteLeave(async () => {
  if (!hasPendingEdits()) return true;
  return confirm({
    title: t("settings.scan-leave-title"),
    body: t("settings.scan-leave-body"),
    confirmText: t("settings.scan-leave-confirm"),
    tone: "warning",
  });
});

function onBeforeUnload(e: BeforeUnloadEvent) {
  if (!hasPendingEdits()) return;
  e.preventDefault();
  // Legacy browsers require returnValue to be set to trigger the prompt.
  e.returnValue = "";
}

onMounted(() => window.addEventListener("beforeunload", onBeforeUnload));
onBeforeUnmount(() =>
  window.removeEventListener("beforeunload", onBeforeUnload),
);
</script>

<template>
  <div v-if="loading" class="r-v2-scan-settings__loading">
    <RSpinner />
  </div>
  <div v-else-if="loadError" class="r-v2-section-stack r-v2-scan-settings">
    <RAlert type="error">
      <template #title>
        {{ t("settings.scan-settings-load-error-title") }}
      </template>
      {{ t("settings.scan-settings-load-error-desc") }}
      <template #actions>
        <RBtn variant="text" :loading="loading" @click="loadConfig">
          {{ t("common.try-again") }}
        </RBtn>
      </template>
    </RAlert>
  </div>
  <div v-else class="r-v2-section-stack r-v2-scan-settings">
    <RAlert v-if="!config.CONFIG_FILE_MOUNTED" type="error">
      <template #title>
        {{ t("settings.config-file-not-mounted-title") }}
      </template>
      {{ t("settings.config-file-not-mounted-desc") }}
    </RAlert>
    <RAlert
      v-if="config.CONFIG_FILE_MOUNTED && config.CONFIG_FILE_PARSE_ERROR"
      type="error"
    >
      <template #title>
        {{ t("settings.config-file-parse-error-title") }}
      </template>
      {{
        t("settings.config-file-parse-error-desc", {
          error: config.CONFIG_FILE_PARSE_ERROR,
        })
      }}
    </RAlert>
    <RAlert
      v-if="config.CONFIG_FILE_MOUNTED && !config.CONFIG_FILE_WRITABLE"
      type="warning"
    >
      <template #title>
        {{ t("settings.config-file-not-writable-title") }}
      </template>
      {{ t("settings.config-file-not-writable-desc") }}
    </RAlert>

    <!-- Metadata priority -->
    <SettingsSection
      :title="t('settings.scan-metadata-priority')"
      icon="mdi-database-cog-outline"
    >
      <p class="r-v2-scan-settings__desc">
        {{ t("settings.scan-metadata-priority-desc") }}
      </p>
      <ScanPriorityList
        v-model="form.metadata"
        :sources="METADATA_SOURCES"
        :disabled="!canEdit"
      />
    </SettingsSection>

    <!-- Artwork priority + per-field overrides -->
    <SettingsSection
      :title="t('settings.scan-artwork-priority')"
      icon="mdi-image-multiple-outline"
    >
      <p class="r-v2-scan-settings__desc">
        {{ t("settings.scan-artwork-priority-desc") }}
      </p>
      <ScanPriorityList
        v-model="form.artwork"
        :sources="ARTWORK_SOURCES"
        :disabled="!canEdit"
      />

      <SettingsSubsection
        :title="t('settings.scan-artwork-overrides')"
        icon="mdi-tune-variant"
      >
        <p class="r-v2-scan-settings__desc mb-4">
          {{ t("settings.scan-artwork-overrides-desc") }}
        </p>
        <SettingsToggleRow
          v-model="form.coverEnabled"
          :title="t('settings.scan-override-cover')"
          :disabled="!canEdit"
        />
        <ScanPriorityList
          v-if="form.coverEnabled"
          v-model="form.cover"
          :sources="ARTWORK_SOURCES"
          :disabled="!canEdit"
        />
        <SettingsToggleRow
          v-model="form.screenshotEnabled"
          :title="t('settings.scan-override-screenshot')"
          :disabled="!canEdit"
        />
        <ScanPriorityList
          v-if="form.screenshotEnabled"
          v-model="form.screenshot"
          :sources="ARTWORK_SOURCES"
          :disabled="!canEdit"
        />
        <SettingsToggleRow
          v-model="form.manualEnabled"
          :title="t('settings.scan-override-manual')"
          :disabled="!canEdit"
        />
        <ScanPriorityList
          v-if="form.manualEnabled"
          v-model="form.manual"
          :sources="ARTWORK_SOURCES"
          :disabled="!canEdit"
        />
      </SettingsSubsection>
    </SettingsSection>

    <!-- Region priority -->
    <SettingsSection
      :title="t('settings.scan-region-priority')"
      icon="mdi-earth"
    >
      <div class="r-v2-scan-settings__field">
        <p class="r-v2-scan-settings__desc">
          {{ t("settings.scan-region-priority-desc") }}
        </p>
        <RComboboxField
          v-model="form.region"
          :items="REGION_SUGGESTIONS"
          :placeholder="t('settings.scan-region-placeholder')"
          :disabled="!canEdit"
          hide-details
        />
      </div>
    </SettingsSection>

    <!-- Language priority -->
    <SettingsSection
      :title="t('settings.scan-language-priority')"
      icon="mdi-translate"
    >
      <div class="r-v2-scan-settings__field">
        <p class="r-v2-scan-settings__desc">
          {{ t("settings.scan-language-priority-desc") }}
        </p>
        <RComboboxField
          v-model="form.language"
          :items="LANGUAGE_SUGGESTIONS"
          :placeholder="t('settings.scan-language-placeholder')"
          :disabled="!canEdit"
          hide-details
        />
      </div>
    </SettingsSection>

    <!-- Media types -->
    <SettingsSection :title="t('settings.scan-media')" icon="mdi-multimedia">
      <div class="r-v2-scan-settings__field">
        <p class="r-v2-scan-settings__desc">
          {{ t("settings.scan-media-desc") }}
        </p>
        <RSelect
          :model-value="form.media"
          :items="mediaItems"
          multiple
          searchable
          :disabled="!canEdit"
          :placeholder="t('settings.scan-media-placeholder')"
          hide-details
          @update:model-value="setMedia"
        />
        <p class="r-v2-scan-settings__note">
          <RIcon icon="mdi-information-outline" size="13" />
          {{ t("settings.scan-media-note") }}
        </p>
      </div>
    </SettingsSection>

    <!-- Gamelist export -->
    <SettingsSection
      :title="t('settings.scan-gamelist')"
      icon="mdi-file-export-outline"
    >
      <div
        class="r-v2-scan-settings__toggle-grid r-v2-scan-settings__toggle-grid--single"
      >
        <SettingsToggleRow
          v-model="form.gamelistExport"
          :title="t('settings.scan-gamelist-export')"
          :description="t('settings.scan-gamelist-export-desc')"
          :disabled="!canEdit"
        />
      </div>
      <div
        class="r-v2-scan-settings__field r-v2-scan-settings__field--bordered"
      >
        <RSelect
          v-model="form.gamelistThumbnail"
          :items="thumbnailItems"
          prefix-label="stacked"
          :disabled="!canEdit || !form.gamelistExport"
          hide-details
        >
          <template #prefix-label>
            {{ t("settings.scan-gamelist-thumbnail") }}
          </template>
        </RSelect>
        <RSelect
          v-model="form.gamelistImage"
          :items="imageItems"
          prefix-label="stacked"
          :disabled="!canEdit || !form.gamelistExport"
          hide-details
        >
          <template #prefix-label>
            {{ t("settings.scan-gamelist-image") }}
          </template>
        </RSelect>
      </div>
    </SettingsSection>

    <!-- Pegasus export -->
    <SettingsSection
      :title="t('settings.scan-pegasus')"
      icon="mdi-file-export-outline"
    >
      <div
        class="r-v2-scan-settings__toggle-grid r-v2-scan-settings__toggle-grid--single"
      >
        <SettingsToggleRow
          v-model="form.pegasusExport"
          :title="t('settings.scan-pegasus-export')"
          :description="t('settings.scan-pegasus-export-desc')"
          :disabled="!canEdit"
        />
      </div>
    </SettingsSection>

    <!-- Sticky save bar — appears once the form diverges from the saved
         config. Hidden entirely when the user can't edit. -->
    <Transition name="r-v2-scan-settings__bar">
      <div v-if="dirty && canEdit" class="r-v2-scan-settings__bar">
        <span class="r-v2-scan-settings__bar-label">
          {{ t("settings.scan-unsaved-changes") }}
        </span>
        <div class="r-v2-scan-settings__bar-actions">
          <RBtn variant="text" :disabled="saving" @click="onReset">
            {{ t("common.discard") }}
          </RBtn>
          <RBtn
            variant="flat"
            color="primary"
            prepend-icon="mdi-content-save-outline"
            :loading="saving"
            @click="onSave"
          >
            {{ t("common.save") }}
          </RBtn>
        </div>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.r-v2-scan-settings__loading {
  display: grid;
  place-items: center;
  min-height: 240px;
}

/* Extra bottom padding so the sticky save bar never covers the last
   section's controls. */
.r-v2-scan-settings {
  padding-bottom: 72px;
}

.r-v2-scan-settings__desc {
  margin: 0;
  padding: 16px 16px 0;
  color: var(--r-color-fg-muted);
  font-size: 13px;
  line-height: 1.5;
  max-width: 680px;
}
/* When a description sits directly above a field block, drop its bottom
   padding so the field's own padding provides the gap. */
.r-v2-scan-settings__field .r-v2-scan-settings__desc {
  padding: 0;
}

.r-v2-scan-settings__field {
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.r-v2-scan-settings__field--bordered {
  border-top: 1px solid var(--r-color-border);
}

.r-v2-scan-settings__note {
  margin: 0;
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--r-color-fg-faint);
}

.r-v2-scan-settings__toggle-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1px;
  background: var(--r-color-border);
}
.r-v2-scan-settings__toggle-grid--single {
  grid-template-columns: 1fr;
}
html[data-bp~="xs"] .r-v2-scan-settings__toggle-grid {
  grid-template-columns: 1fr;
}

/* Sticky save bar pinned to the bottom of the content column. */
.r-v2-scan-settings__bar {
  position: sticky;
  bottom: 16px;
  z-index: 2;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-top: 8px;
  padding: 12px 16px;
  border-radius: 12px;
  background: var(--r-color-panel);
  border: 1px solid var(--r-color-panel-border);
  box-shadow: 0 12px 32px color-mix(in srgb, black 32%, transparent);
}
.r-v2-scan-settings__bar-label {
  font-size: 13px;
  font-weight: var(--r-font-weight-medium);
  color: var(--r-color-fg-secondary);
}
.r-v2-scan-settings__bar-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.r-v2-scan-settings__bar-enter-active,
.r-v2-scan-settings__bar-leave-active {
  transition:
    opacity var(--r-motion-med) var(--r-motion-ease-out),
    transform var(--r-motion-med) var(--r-motion-ease-out);
}
.r-v2-scan-settings__bar-enter-from,
.r-v2-scan-settings__bar-leave-to {
  opacity: 0;
  transform: translateY(8px);
}
@media (prefers-reduced-motion: reduce) {
  .r-v2-scan-settings__bar-enter-from,
  .r-v2-scan-settings__bar-leave-to {
    transform: none;
  }
}
</style>
