<script setup lang="ts">
import {
  RBtn,
  RDivider,
  REmptyState,
  RProgressCircular,
  RSelect,
  RSpinner,
  RTextField,
} from "@v2/lib";
import { storeToRefs } from "pinia";
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import configApi from "@/services/api/config";
import installApi from "@/services/api/install";
import type { ProtonBuildExtended } from "@/services/api/install";
import storeAuth from "@/stores/auth";
import type { Config } from "@/stores/config";
import storeConfig from "@/stores/config";
import { useSnackbar } from "@/v2/composables/useSnackbar";
import AddProtonBuildDialog from "./AddProtonBuildDialog.vue";
import InstallCacheManager from "./InstallCacheManager.vue";
import SettingsSection from "./SettingsSection.vue";
import SettingsToggleRow from "./SettingsToggleRow.vue";

const { t } = useI18n();
const snackbar = useSnackbar();
const authStore = storeAuth();
const configStore = storeConfig();
const { config } = storeToRefs(configStore);

const KB = 1024;

function configToKbPerSec(cfg: Config): number | null {
  const bytesPerSec = cfg.INSTALL_DOWNLOAD_SPEED_LIMIT_BYTES_PER_SEC;
  return bytesPerSec ? Math.round(bytesPerSec / KB) : null;
}

const kbPerSec = ref<number | null>(configToKbPerSec(config.value));
const savedSnapshot = ref(kbPerSec.value);

const cacheTtlDays = ref<number | null>(
  (config.value as Config).INSTALL_CACHE_TTL_DAYS ?? 0,
);
const savedCacheTtlDays = ref(cacheTtlDays.value);
const addBuildOpen = ref(false);

const protonBuilds = ref<ProtonBuildExtended[]>([]);
const selectedProtonBuild = ref<string | null>(
  config.value.INSTALL_DEFAULT_PROTON_BUILD,
);
const savedProtonBuild = ref<string | null>(selectedProtonBuild.value);
const downloadingBuilds = ref<Record<string, number>>({});
const loadingBuilds = ref(false);

const streamUncompletedFiles = ref(
  config.value.INSTALL_STREAM_UNCOMPLETED_FILES,
);
const savedStreamUncompletedFiles = ref(streamUncompletedFiles.value);

const autoMode = ref((config.value as Config).INSTALL_AUTO_MODE ?? false);
const savedAutoMode = ref(autoMode.value);

const dirty = computed(() => {
  if (kbPerSec.value !== savedSnapshot.value) return true;
  if (selectedProtonBuild.value !== savedProtonBuild.value) return true;
  if (cacheTtlDays.value !== savedCacheTtlDays.value) return true;
  if (streamUncompletedFiles.value !== savedStreamUncompletedFiles.value)
    return true;
  if (autoMode.value !== savedAutoMode.value) return true;
  return false;
});

const canEdit = computed(
  () =>
    authStore.scopes.includes("platforms.write") &&
    config.value.CONFIG_FILE_WRITABLE,
);
const canDownload = computed(() => authStore.scopes.includes("roms.install"));

const loading = ref(true);
const saving = ref(false);

async function loadConfig() {
  loading.value = true;
  try {
    const cfg = await configStore.fetchConfig({ rethrow: true });
    kbPerSec.value = configToKbPerSec(cfg);
    savedSnapshot.value = kbPerSec.value;
    selectedProtonBuild.value = cfg.INSTALL_DEFAULT_PROTON_BUILD ?? null;
    savedProtonBuild.value = selectedProtonBuild.value;
    cacheTtlDays.value = (cfg as Config).INSTALL_CACHE_TTL_DAYS ?? 0;
    savedCacheTtlDays.value = cacheTtlDays.value;
    streamUncompletedFiles.value = cfg.INSTALL_STREAM_UNCOMPLETED_FILES;
    savedStreamUncompletedFiles.value = streamUncompletedFiles.value;
    autoMode.value = (cfg as Config).INSTALL_AUTO_MODE ?? false;
    savedAutoMode.value = autoMode.value;
  } catch {
    // Best-effort: the section still renders with whatever the store
    // already had (e.g. from a previous successful load).
  } finally {
    loading.value = false;
  }
}

async function loadProtonBuilds() {
  loadingBuilds.value = true;
  try {
    const { data } = await installApi.getProtonBuilds();
    protonBuilds.value = data.builds;
  } catch {
    protonBuilds.value = [];
  } finally {
    loadingBuilds.value = false;
  }
}

onMounted(() => {
  loadConfig();
  loadProtonBuilds();
});

function onReset() {
  kbPerSec.value = savedSnapshot.value;
  selectedProtonBuild.value = savedProtonBuild.value;
  cacheTtlDays.value = savedCacheTtlDays.value;
  streamUncompletedFiles.value = savedStreamUncompletedFiles.value;
  autoMode.value = savedAutoMode.value;
}

async function onSave() {
  saving.value = true;
  try {
    const bytesPerSec =
      kbPerSec.value && kbPerSec.value > 0
        ? Math.round(kbPerSec.value * KB)
        : null;
    await configApi.updateInstallSettings({
      download_speed_limit_bytes_per_sec: bytesPerSec,
      default_proton_build: selectedProtonBuild.value,
      stream_uncompleted_files: streamUncompletedFiles.value,
      cache_ttl_days: Math.max(0, Math.floor(Number(cacheTtlDays.value) || 0)),
      auto_mode: autoMode.value,
    });
    savedSnapshot.value = kbPerSec.value;
    savedProtonBuild.value = selectedProtonBuild.value;
    savedCacheTtlDays.value = cacheTtlDays.value;
    savedStreamUncompletedFiles.value = streamUncompletedFiles.value;
    savedAutoMode.value = autoMode.value;
    await configStore.fetchConfig();
    snackbar.success(t("settings.stream-install-saved"));
  } catch (err) {
    const e = err as {
      response?: { data?: { detail?: string }; statusText?: string };
      message?: string;
    };
    const detail =
      e?.response?.data?.detail || e?.response?.statusText || e?.message;
    snackbar.error(t("settings.stream-install-save-error", { detail }));
  } finally {
    saving.value = false;
  }
}

let downloadPollTimer: ReturnType<typeof setTimeout> | null = null;
let stopped = false;

async function startDownload(buildId: string) {
  downloadingBuilds.value[buildId] = 0;
  try {
    await installApi.downloadProtonBuild(buildId);
    scheduleDownloadPoll(buildId);
  } catch (err) {
    const e = err as {
      response?: { data?: { detail?: string }; statusText?: string };
      message?: string;
    };
    const detail =
      e?.response?.data?.detail || e?.response?.statusText || e?.message;
    snackbar.error(
      t("rom.install-proton-download-failed", { name: buildId, detail }),
    );
    delete downloadingBuilds.value[buildId];
  }
}

const DOWNLOAD_POLL_INTERVAL_MS = 2000;

function scheduleDownloadPoll(buildId: string) {
  if (downloadPollTimer !== null) clearTimeout(downloadPollTimer);
  if (stopped) return;
  downloadPollTimer = setTimeout(
    () => pollDownloadProgress(buildId),
    DOWNLOAD_POLL_INTERVAL_MS,
  );
}

async function pollDownloadProgress(buildId: string) {
  try {
    const { data } = await installApi.getProtonDownloadProgress(buildId);
    if (data.extracting) {
      downloadingBuilds.value[buildId] = -1; // indeterminate spinner
      scheduleDownloadPoll(buildId);
    } else if (data.progress === null) {
      downloadPollTimer = null;
      await loadProtonBuilds();
      delete downloadingBuilds.value[buildId];
      snackbar.success(
        t("rom.install-proton-download-complete", { name: buildId }),
      );
    } else {
      downloadingBuilds.value[buildId] = data.progress;
      scheduleDownloadPoll(buildId);
    }
  } catch {
    downloadPollTimer = null;
    delete downloadingBuilds.value[buildId];
  }
}

onBeforeUnmount(() => {
  stopped = true;
  if (downloadPollTimer !== null) clearTimeout(downloadPollTimer);
});

const allBuilds = computed(() => protonBuilds.value);

async function removeCustomBuild(buildId: string) {
  try {
    await installApi.deleteCustomProtonBuild(buildId);
    if (selectedProtonBuild.value === buildId) selectedProtonBuild.value = null;
    await loadProtonBuilds();
  } catch (err) {
    const e = err as {
      response?: { data?: { detail?: string } };
      message?: string;
    };
    snackbar.error(
      t("settings.stream-install-custom-remove-error", {
        detail: e?.response?.data?.detail || e?.message || "",
      }),
    );
  }
}

const downloadableBuilds = computed(() =>
  protonBuilds.value.filter((b) => !b.installed),
);
</script>

<template>
  <div class="r-v2-stream-install">
    <SettingsSection
      :title="t('settings.stream-install-speed-limit')"
      icon="mdi-speedometer"
    >
      <div class="r-v2-stream-install__body">
        <p class="r-v2-stream-install__desc">
          {{ t("settings.stream-install-speed-limit-desc") }}
        </p>
        <RTextField
          v-model="kbPerSec"
          type="number"
          min="0"
          :disabled="!canEdit || loading"
          :label="t('settings.stream-install-speed-limit-field')"
          :placeholder="t('settings.stream-install-unlimited')"
          :hint="t('settings.stream-install-unlimited-hint')"
          class="r-v2-stream-install__field"
        >
          <template #append-inner>
            <span class="r-v2-stream-install__unit">KB/s</span>
          </template>
        </RTextField>
      </div>
    </SettingsSection>

    <SettingsSection
      :title="t('settings.stream-install-proton-title')"
      icon="mdi-water-check"
    >
      <div class="r-v2-stream-install__body">
        <p class="r-v2-stream-install__desc">
          {{ t("settings.stream-install-proton-desc") }}
        </p>

        <div class="r-v2-stream-install__proton-pick">
          <RSelect
            v-model="selectedProtonBuild"
            :items="allBuilds"
            :label="t('settings.stream-install-proton-field')"
            :disabled="!canEdit || loading"
            :loading="loadingBuilds"
            item-title="label"
            item-value="id"
          />
          <RBtn
            variant="outlined"
            icon="mdi-plus"
            :aria-label="t('settings.stream-install-custom-title')"
            :title="t('settings.stream-install-custom-title')"
            :disabled="!canEdit"
            @click="addBuildOpen = true"
          />
        </div>
        <AddProtonBuildDialog
          v-model="addBuildOpen"
          @added="loadProtonBuilds"
        />

        <REmptyState
          v-if="protonBuilds.length === 0 && !loadingBuilds"
          icon="mdi-package-variant"
          :title="t('rom.install-proton-no-installs')"
        />

        <RDivider class="r-v2-stream-install__builds-divider">
          {{ t("rom.install-proton-available-downloads") }}
        </RDivider>

        <div
          v-for="build in downloadableBuilds"
          :key="build.id"
          class="r-v2-stream-install__build-row"
        >
          <div class="r-v2-stream-install__build-info">
            <span class="r-v2-stream-install__build-label">{{
              build.label
            }}</span>
            <span class="r-v2-stream-install__build-badge">
              {{ t("rom.install-proton-downloadable") }}
            </span>
          </div>
          <RBtn
            v-if="build.custom && downloadingBuilds[build.id] === undefined"
            variant="text"
            size="small"
            color="error"
            icon="mdi-delete-outline"
            :aria-label="t('common.delete')"
            :disabled="!canEdit"
            @click="removeCustomBuild(build.id)"
          />

          <div
            v-if="downloadingBuilds[build.id] !== undefined"
            class="r-v2-stream-install__build-progress"
          >
            <RProgressCircular
              :model-value="Math.max(0, downloadingBuilds[build.id]) * 100"
              :indeterminate="downloadingBuilds[build.id] <= 0"
              :size="16"
              :label="
                t('rom.install-proton-downloading', {
                  progress: Math.round(
                    Math.max(0, downloadingBuilds[build.id]) * 100,
                  ),
                })
              "
            />
            <span class="r-v2-stream-install__build-progress-text">
              {{ Math.round((downloadingBuilds[build.id] || 0) * 100) }}%
            </span>
          </div>

          <RBtn
            v-else
            variant="flat"
            color="primary"
            size="small"
            :loading="false"
            :disabled="!canEdit || !canDownload"
            @click="startDownload(build.id)"
          >
            {{ t("rom.install-proton-download-btn") }}
          </RBtn>
        </div>

        <div v-if="loadingBuilds" class="r-v2-stream-install__builds-loading">
          <RSpinner />
        </div>
      </div>
    </SettingsSection>

    <SettingsSection
      :title="t('settings.install-cache-title')"
      icon="mdi-database-outline"
    >
      <div class="r-v2-stream-install__body">
        <p class="r-v2-stream-install__desc">
          {{ t("settings.install-cache-ttl-desc") }}
        </p>
        <RTextField
          v-model.number="cacheTtlDays"
          type="number"
          min="0"
          :disabled="!canEdit || loading"
          :label="t('settings.install-cache-ttl-field')"
          :hint="t('settings.install-cache-ttl-hint')"
          persistent-hint
          class="r-v2-stream-install__field"
        >
          <template #append-inner>
            <span class="r-v2-stream-install__unit">
              {{ t("settings.install-cache-ttl-unit") }}
            </span>
          </template>
        </RTextField>
        <RDivider class="r-v2-stream-install__cache-divider" />
        <InstallCacheManager :can-edit="canEdit" />
      </div>
    </SettingsSection>

    <SettingsSection
      :title="t('settings.stream-install-experimental-title')"
      icon="mdi-flask-outline"
    >
      <SettingsToggleRow
        v-model="streamUncompletedFiles"
        :title="t('settings.stream-install-uncompleted-files')"
        :description="t('settings.stream-install-uncompleted-files-desc')"
        :disabled="!canEdit || loading"
      />
      <SettingsToggleRow
        v-model="autoMode"
        :title="t('settings.stream-install-auto-mode')"
        :description="t('settings.stream-install-auto-mode-desc')"
        :disabled="!canEdit || loading"
      />
    </SettingsSection>

    <Transition name="r-v2-stream-install__bar">
      <div v-if="dirty && canEdit" class="r-v2-stream-install__bar">
        <span class="r-v2-stream-install__bar-label">
          {{ t("settings.scan-unsaved-changes") }}
        </span>
        <div class="r-v2-stream-install__bar-actions">
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
.r-v2-stream-install {
  display: flex;
  flex-direction: column;
  gap: 20px;
}
.r-v2-stream-install__body {
  padding: 16px;
}
.r-v2-stream-install__desc {
  margin: 0 0 12px;
  font-size: 13px;
  color: var(--r-color-fg-muted);
}
.r-v2-stream-install__field {
  max-width: 280px;
}
.r-v2-stream-install__proton-pick {
  display: flex;
  align-items: flex-start;
  gap: 8px;
}
.r-v2-stream-install__proton-pick > :first-child {
  flex: 1;
  min-width: 0;
}
.r-v2-stream-install__cache-divider {
  margin: 16px 0;
}
.r-v2-stream-install__unit {
  font-size: 12px;
  color: var(--r-color-fg-muted);
}

.r-v2-stream-install__bar {
  position: sticky;
  bottom: 16px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 16px;
  background: var(--r-color-bg-elevated);
  border: 1px solid var(--r-color-border);
  border-radius: var(--r-radius-md);
  box-shadow: 0 8px 24px color-mix(in srgb, black 30%, transparent);
}
.r-v2-stream-install__bar-label {
  font-size: 13px;
  color: var(--r-color-fg-secondary);
}
.r-v2-stream-install__bar-actions {
  display: flex;
  gap: 8px;
}
.r-v2-stream-install__bar-enter-active,
.r-v2-stream-install__bar-leave-active {
  transition:
    opacity var(--r-motion-med) var(--r-motion-ease-out),
    transform var(--r-motion-med) var(--r-motion-ease-out);
}
.r-v2-stream-install__bar-enter-from,
.r-v2-stream-install__bar-leave-to {
  opacity: 0;
  transform: translateY(8px);
}

.r-v2-stream-install__builds-divider {
  margin: 16px 0 8px;
  font-size: 11px;
  font-weight: var(--r-font-weight-bold);
  letter-spacing: 0.1em;
  text-transform: uppercase;
}
.r-v2-stream-install__build-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 0;
  border-bottom: 1px solid var(--r-color-border);
}
.r-v2-stream-install__build-row:last-child {
  border-bottom: none;
}
.r-v2-stream-install__build-info {
  display: flex;
  align-items: center;
  gap: 8px;
}
.r-v2-stream-install__build-label {
  font-size: 13px;
  color: var(--r-color-fg-primary);
}
.r-v2-stream-install__build-badge {
  font-size: 11px;
  padding: 2px 8px;
  background: var(--r-color-surface-elevated);
  color: var(--r-color-fg-muted);
  border-radius: 4px;
}
.r-v2-stream-install__build-progress {
  display: flex;
  align-items: center;
  gap: 6px;
}
.r-v2-stream-install__build-progress-text {
  font-size: 12px;
  color: var(--r-color-fg-muted);
}
.r-v2-stream-install__builds-loading {
  padding: 12px;
  display: flex;
  justify-content: center;
}
</style>
