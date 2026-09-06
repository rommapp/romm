<script setup lang="ts">
// Editor for the converto.* section of config.yml: download-time
// conversion, scan metadata extraction, cache TTL and the platform to
// target-format mapping.
import { RAlert, RIcon, RSelect, RTextField, RBtn, RSpinner } from "@v2/lib";
import { storeToRefs } from "pinia";
import { computed, onBeforeUnmount, onMounted, reactive, ref } from "vue";
import { useI18n } from "vue-i18n";
import { onBeforeRouteLeave } from "vue-router";
import type { ConvertoSettingsPayload } from "@/__generated__";
import configApi from "@/services/api/config";
import storeAuth from "@/stores/auth";
import storeConfig, { type Config } from "@/stores/config";
import storePlatforms from "@/stores/platforms";
import SettingsSection from "@/v2/components/Settings/SettingsSection.vue";
import SettingsToggleRow from "@/v2/components/Settings/SettingsToggleRow.vue";
import { useConfirm } from "@/v2/composables/useConfirm";
import { useSnackbar } from "@/v2/composables/useSnackbar";

const { t } = useI18n();
const confirm = useConfirm();
const configStore = storeConfig();
const { config } = storeToRefs(configStore);
const authStore = storeAuth();
const platformsStore = storePlatforms();
const snackbar = useSnackbar();

// Platforms and their targets come from the backend, which owns the
// rom-converto operation table.
const platforms = computed(() =>
  Object.keys(config.value.CONVERTO_TARGETS)
    .sort()
    .map((slug) => ({
      slug,
      label:
        platformsStore.allPlatforms.find((p) => p.slug === slug)
          ?.display_name ?? slug,
    })),
);

function formatItems(slug: string) {
  return [
    { title: t("settings.conversion-platform-formats-original"), value: "" },
    ...(config.value.CONVERTO_TARGETS[slug] ?? []).map((value) => ({
      title: value,
      value,
    })),
  ];
}

interface ConversionForm {
  downloadConversionEnabled: boolean;
  scanMetadata: boolean;
  cacheTtlHours: number | null;
  // Platform slug to target; empty string keeps the original file.
  formats: Record<string, string>;
}

function configToForm(cfg: Config): ConversionForm {
  const saved = cfg.CONVERTO.platform_formats;
  const formats: Record<string, string> = {};
  for (const [slug, targets] of Object.entries(cfg.CONVERTO_TARGETS)) {
    const target = saved[slug];
    formats[slug] = target && targets.includes(target) ? target : "";
  }
  return {
    downloadConversionEnabled: cfg.CONVERTO.download_conversion_enabled,
    scanMetadata: cfg.CONVERTO.scan_metadata,
    cacheTtlHours: cfg.CONVERTO.cache_ttl_hours,
    formats,
  };
}

function formToPayload(f: ConversionForm): ConvertoSettingsPayload {
  const platformFormats: Record<string, string> = {};
  for (const [slug, target] of Object.entries(f.formats)) {
    if (target) platformFormats[slug] = target;
  }
  return {
    download_conversion_enabled: f.downloadConversionEnabled,
    scan_metadata: f.scanMetadata,
    cache_ttl_hours: f.cacheTtlHours ?? 1,
    platform_formats: platformFormats,
  };
}

const form = reactive<ConversionForm>(configToForm(config.value));
// Snapshot of the last-saved payload, for dirty detection.
const savedSnapshot = ref(JSON.stringify(formToPayload(form)));

const cacheTtlValid = computed(
  () =>
    form.cacheTtlHours !== null &&
    Number.isInteger(form.cacheTtlHours) &&
    form.cacheTtlHours >= 1,
);

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

function onReset() {
  resetForm(config.value);
}

async function onSave() {
  saving.value = true;
  try {
    await configApi.updateConvertoSettings(formToPayload(form));
    // The backend normalizes slugs and targets; snapshot what it stored.
    resetForm(await configStore.fetchConfig({ rethrow: true }));
    snackbar.success(t("settings.conversion-settings-saved"));
  } catch (err) {
    const e = err as {
      response?: { data?: { detail?: string }; statusText?: string };
      message?: string;
    };
    const detail =
      e.response?.data?.detail ||
      e.response?.statusText ||
      e.message ||
      t("common.unknown-error");
    snackbar.error(t("settings.conversion-settings-save-error", { detail }));
  } finally {
    saving.value = false;
  }
}

function setCacheTtl(value: unknown) {
  const parsed = Number.parseInt(String(value), 10);
  form.cacheTtlHours = Number.isNaN(parsed) ? null : parsed;
}

const hasPendingEdits = () => dirty.value && canEdit.value;

onBeforeRouteLeave(async () => {
  if (!hasPendingEdits()) return true;
  return confirm({
    title: t("settings.conversion-leave-title"),
    body: t("settings.conversion-leave-body"),
    confirmText: t("settings.conversion-leave-confirm"),
    tone: "warning",
  });
});

function onBeforeUnload(e: BeforeUnloadEvent) {
  if (!hasPendingEdits()) return;
  e.preventDefault();
  // Legacy browsers require returnValue to be set to trigger the prompt.
  e.returnValue = "";
}

onMounted(() => {
  window.addEventListener("beforeunload", onBeforeUnload);
  void loadConfig();
});
onBeforeUnmount(() =>
  window.removeEventListener("beforeunload", onBeforeUnload),
);
</script>

<template>
  <div v-if="loading" class="r-v2-conversion-settings__loading">
    <RSpinner />
  </div>
  <div v-else-if="loadError" class="r-v2-section-stack r-v2-conversion-settings">
    <RAlert type="error">
      <template #title>
        {{ t("settings.conversion-settings-load-error-title") }}
      </template>
      {{ t("settings.conversion-settings-load-error-desc") }}
      <template #append>
        <RBtn variant="text" :loading="loading" @click="loadConfig">
          {{ t("common.try-again") }}
        </RBtn>
      </template>
    </RAlert>
  </div>
  <div
    v-else
    class="r-v2-section-stack r-v2-conversion-settings"
  >
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

    <!-- Download conversion -->
    <SettingsSection
      :title="t('settings.conversion-download-title')"
      icon="mdi-swap-horizontal"
    >
      <SettingsToggleRow
        v-model="form.downloadConversionEnabled"
        :title="t('settings.conversion-download-conversion-enabled')"
        :description="t('settings.conversion-download-conversion-enabled-desc')"
        :disabled="!canEdit"
      />
      <SettingsToggleRow
        v-model="form.scanMetadata"
        :title="t('settings.conversion-scan-metadata')"
        :description="t('settings.conversion-scan-metadata-desc')"
        :disabled="!canEdit"
      />
      <div class="r-v2-conversion-settings__field">
        <RTextField
          :model-value="form.cacheTtlHours"
          type="number"
          min="1"
          step="1"
          :label="t('settings.conversion-cache-ttl-hours')"
          :disabled="!canEdit"
          :hide-details="cacheTtlValid"
          :error-messages="
            cacheTtlValid
              ? []
              : [t('settings.conversion-cache-ttl-hours-invalid')]
          "
          @update:model-value="setCacheTtl"
        />
        <p class="r-v2-conversion-settings__note">
          <RIcon icon="mdi-information-outline" size="13" />
          {{ t("settings.conversion-cache-ttl-hours-desc") }}
        </p>
      </div>
    </SettingsSection>

    <!-- Platform → target format mapping -->
    <SettingsSection
      :title="t('settings.conversion-platform-formats')"
      icon="mdi-disc"
    >
      <p class="r-v2-conversion-settings__desc">
        {{ t("settings.conversion-platform-formats-desc") }}
      </p>
      <div class="r-v2-conversion-settings__formats">
        <div
          v-for="platform in platforms"
          :key="platform.slug"
          class="r-v2-conversion-settings__format-row"
        >
          <span class="r-v2-conversion-settings__format-label">
            {{ platform.label }}
          </span>
          <RSelect
            v-model="form.formats[platform.slug]"
            :items="formatItems(platform.slug)"
            :label="platform.label"
            :disabled="!canEdit"
            hide-details
          />
        </div>
      </div>
    </SettingsSection>

    <Transition name="r-v2-conversion-settings__bar">
      <div
        v-if="dirty && canEdit"
        class="r-v2-conversion-settings__bar"
      >
        <span class="r-v2-conversion-settings__bar-label">
          {{ t("settings.conversion-unsaved-changes") }}
        </span>
        <div class="r-v2-conversion-settings__bar-actions">
          <RBtn variant="text" :disabled="saving" @click="onReset">
            {{ t("common.discard") }}
          </RBtn>
          <RBtn
            variant="flat"
            color="primary"
            prepend-icon="mdi-content-save-outline"
            :loading="saving"
            :disabled="!cacheTtlValid"
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
.r-v2-conversion-settings__loading {
  display: grid;
  place-items: center;
  min-height: 240px;
}

/* Extra bottom padding so the sticky save bar never covers the last
   section's controls. */
.r-v2-conversion-settings {
  padding-bottom: 72px;
}

.r-v2-conversion-settings__desc {
  margin: 0;
  padding: 16px 16px 0;
  color: var(--r-color-fg-muted);
  font-size: 13px;
  line-height: 1.5;
  max-width: 680px;
}

.r-v2-conversion-settings__field {
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.r-v2-conversion-settings__note {
  margin: 0;
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--r-color-fg-faint);
}

.r-v2-conversion-settings__formats {
  padding: 8px 16px 16px;
  display: flex;
  flex-direction: column;
}

.r-v2-conversion-settings__format-row {
  display: grid;
  grid-template-columns: minmax(140px, 220px) minmax(180px, 260px);
  align-items: center;
  gap: 16px;
  padding: 8px 0;
}
html[data-bp~="xs"] .r-v2-conversion-settings__format-row {
  grid-template-columns: 1fr;
}

.r-v2-conversion-settings__format-label {
  font-size: 13px;
  color: var(--r-color-fg-secondary);
}

/* Sticky save bar pinned to the bottom of the content column. */
.r-v2-conversion-settings__bar {
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
.r-v2-conversion-settings__bar-label {
  font-size: 13px;
  font-weight: var(--r-font-weight-medium);
  color: var(--r-color-fg-secondary);
}
.r-v2-conversion-settings__bar-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.r-v2-conversion-settings__bar-enter-active,
.r-v2-conversion-settings__bar-leave-active {
  transition:
    opacity var(--r-motion-med) var(--r-motion-ease-out),
    transform var(--r-motion-med) var(--r-motion-ease-out);
}
.r-v2-conversion-settings__bar-enter-from,
.r-v2-conversion-settings__bar-leave-to {
  opacity: 0;
  transform: translateY(8px);
}
@media (prefers-reduced-motion: reduce) {
  .r-v2-conversion-settings__bar-enter-from,
  .r-v2-conversion-settings__bar-leave-to {
    transform: none;
  }
}
</style>
