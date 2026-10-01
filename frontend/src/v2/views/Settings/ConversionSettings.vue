<script setup lang="ts">
// Editor for the converto.* section of config.yml: download conversion, its
// cache limit, and the per-platform library format the convert task applies.
import { RAlert, RIcon, RSelect, RTextField, RBtn, RSpinner } from "@v2/lib";
import { storeToRefs } from "pinia";
import { computed, onMounted, reactive, ref } from "vue";
import { useI18n } from "vue-i18n";
import { onBeforeRouteLeave } from "vue-router";
import type { ConvertoSettingsPayload } from "@/__generated__";
import configApi from "@/services/api/config";
import taskApi from "@/services/api/task";
import storeAuth from "@/stores/auth";
import storeConfig, { type Config } from "@/stores/config";
import storePlatforms from "@/stores/platforms";
import ConfigFileAlerts from "@/v2/components/Settings/ConfigFileAlerts.vue";
import SettingsSaveBar from "@/v2/components/Settings/SettingsSaveBar.vue";
import SettingsSection from "@/v2/components/Settings/SettingsSection.vue";
import SettingsToggleRow from "@/v2/components/Settings/SettingsToggleRow.vue";
import { useConfirm } from "@/v2/composables/useConfirm";
import { useSnackbar } from "@/v2/composables/useSnackbar";
import { useUnloadGuard } from "@/v2/composables/useUnloadGuard";
import { errorMessage } from "@/v2/utils/errorMessage";

const { t } = useI18n();
const confirm = useConfirm();
const configStore = storeConfig();
const { config } = storeToRefs(configStore);
const authStore = storeAuth();
const platformsStore = storePlatforms();
const snackbar = useSnackbar();

const platforms = computed(() =>
  Object.entries(config.value.CONVERTO_LIBRARY_TARGETS)
    .map(([slug, targets]) => ({
      slug,
      label:
        platformsStore.allPlatforms.find((p) => p.slug === slug)
          ?.display_name ?? slug,
      items: [
        { title: t("settings.conversion-library-format-leave"), value: "" },
        ...targets.map((value) => ({ title: value, value })),
      ],
    }))
    .sort((a, b) => a.label.localeCompare(b.label)),
);

interface ConversionForm {
  downloadConversionEnabled: boolean;
  cacheMaxSizeGb: number | null;
  // Platform slug to library format; empty string leaves its files as they are.
  formats: Record<string, string>;
}

function configToForm(cfg: Config): ConversionForm {
  const saved = cfg.CONVERTO.platform_formats ?? {};
  const formats: Record<string, string> = {};
  for (const [slug, targets] of Object.entries(cfg.CONVERTO_LIBRARY_TARGETS)) {
    const target = saved[slug];
    formats[slug] = target && targets.includes(target) ? target : "";
  }
  return {
    downloadConversionEnabled:
      cfg.CONVERTO.download_conversion_enabled ?? false,
    cacheMaxSizeGb: cfg.CONVERTO.cache_max_size_gb ?? null,
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
    cache_max_size_gb: f.cacheMaxSizeGb ?? 0,
    platform_formats: platformFormats,
  };
}

const form = reactive<ConversionForm>(configToForm(config.value));
// Snapshot of the last-saved payload, for dirty detection.
const savedSnapshot = ref(JSON.stringify(formToPayload(form)));

const cacheMaxSizeValid = computed(
  () =>
    form.cacheMaxSizeGb !== null &&
    Number.isInteger(form.cacheMaxSizeGb) &&
    form.cacheMaxSizeGb >= 0,
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

const canRunTasks = computed(() => authStore.scopes.includes("tasks.run"));
// The task reads the saved formats, so unsaved edits must not look like they apply.
const canConvertLibrary = computed(
  () =>
    !dirty.value &&
    Object.keys(config.value.CONVERTO.platform_formats ?? {}).length > 0,
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
    const payload = formToPayload(form);
    await configApi.updateConvertoSettings(payload);
    savedSnapshot.value = JSON.stringify(payload);
    snackbar.success(t("settings.conversion-settings-saved"));
    await configStore.fetchConfig();
  } catch (err) {
    const detail = errorMessage(err, t("common.unknown-error"));
    snackbar.error(t("settings.conversion-settings-save-error", { detail }));
  } finally {
    saving.value = false;
  }
}

const startingConversion = ref(false);

async function onConvertLibrary() {
  const ok = await confirm({
    title: t("settings.conversion-convert-library-confirm-title"),
    body: t("settings.conversion-convert-library-confirm-body"),
    confirmText: t("settings.conversion-convert-library-confirm"),
    tone: "danger",
    requireTyped: t("rom.delete-keyword"),
  });
  if (!ok) return;
  startingConversion.value = true;
  try {
    await taskApi.runTask("convert_library");
    snackbar.success(
      t("settings.task-started", {
        title: t("settings.conversion-convert-library"),
      }),
    );
  } catch (err) {
    snackbar.error(errorMessage(err, t("settings.task-failed")));
  } finally {
    startingConversion.value = false;
  }
}

function setCacheMaxSize(value: unknown) {
  const raw = String(value ?? "").trim();
  const parsed = Number(raw);
  form.cacheMaxSizeGb = raw === "" || Number.isNaN(parsed) ? null : parsed;
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

useUnloadGuard(hasPendingEdits);

onMounted(loadConfig);
</script>

<template>
  <div v-if="loading" class="r-v2-conversion-settings__loading">
    <RSpinner />
  </div>
  <div
    v-else-if="loadError"
    class="r-v2-section-stack r-v2-conversion-settings"
  >
    <RAlert type="error">
      <template #title>
        {{ t("settings.conversion-settings-load-error-title") }}
      </template>
      {{ t("settings.conversion-settings-load-error-desc") }}
      <template #actions>
        <RBtn variant="text" :loading="loading" @click="loadConfig">
          {{ t("common.try-again") }}
        </RBtn>
      </template>
    </RAlert>
  </div>
  <div v-else class="r-v2-section-stack r-v2-conversion-settings">
    <ConfigFileAlerts />

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
      <div class="r-v2-conversion-settings__field">
        <RTextField
          :model-value="form.cacheMaxSizeGb"
          type="number"
          prefix-label="stacked"
          min="0"
          step="1"
          :label="t('settings.conversion-cache-max-size-gb')"
          :disabled="!canEdit"
          :hide-details="cacheMaxSizeValid"
          :error-messages="
            cacheMaxSizeValid
              ? []
              : [t('settings.conversion-cache-max-size-gb-invalid')]
          "
          @update:model-value="setCacheMaxSize"
        />
        <p class="r-v2-conversion-settings__note">
          <RIcon icon="mdi-information-outline" size="13" />
          {{ t("settings.conversion-cache-max-size-gb-desc") }}
        </p>
      </div>
    </SettingsSection>

    <SettingsSection
      :title="t('settings.conversion-library-format')"
      icon="mdi-disc"
    >
      <p class="r-v2-conversion-settings__desc">
        {{ t("settings.conversion-library-format-desc") }}
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
            :items="platform.items"
            :label="platform.label"
            :disabled="!canEdit"
            hide-details
          />
        </div>
      </div>
      <div v-if="canRunTasks" class="r-v2-conversion-settings__field">
        <div>
          <RBtn
            variant="outlined"
            color="danger"
            prepend-icon="mdi-swap-horizontal-bold"
            :loading="startingConversion"
            :disabled="!canConvertLibrary"
            @click="onConvertLibrary"
          >
            {{ t("settings.conversion-convert-library") }}
          </RBtn>
        </div>
        <p class="r-v2-conversion-settings__note">
          <RIcon icon="mdi-information-outline" size="13" />
          {{ t("settings.conversion-convert-library-desc") }}
        </p>
      </div>
    </SettingsSection>

    <SettingsSaveBar
      :visible="dirty && canEdit"
      :label="t('settings.conversion-unsaved-changes')"
      :saving="saving"
      :save-disabled="!cacheMaxSizeValid"
      @save="onSave"
      @discard="onReset"
    />
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
</style>
