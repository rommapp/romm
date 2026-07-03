<script setup lang="ts">
// PatcherTab — server-side patch flow for a single ROM, rendered as a tab
// in GameDetails. Picks a base game file and a patch file from the ROM's
// `files`, POSTs to `/roms/{fileId}/patch`, and streams the patched ROM
// back as a blob to download locally and/or re-upload into RomM.
import {
  RAlert,
  RBtn,
  RCheckbox,
  RExpandTransition,
  RIcon,
  RPlatformIcon,
  RSelect,
  RTextField,
  RTooltip,
} from "@v2/lib";
import { storeToRefs } from "pinia";
import { computed, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import type { DetailedRomSchema, RomFileSchema } from "@/__generated__";
import api from "@/services/api";
import romApi from "@/services/api/rom";
import socket from "@/services/socket";
import storeHeartbeat from "@/stores/heartbeat";
import storePlatforms, { type Platform } from "@/stores/platforms";
import storeScanning from "@/stores/scanning";
import storeUpload from "@/stores/upload";
import { formatBytes } from "@/utils";
import MissingFSBadge from "@/v2/components/shared/MissingFSBadge.vue";
import PlatformSelect from "@/v2/components/shared/PlatformSelect.vue";
import { useCan } from "@/v2/composables/useCan";
import { useSnackbar } from "@/v2/composables/useSnackbar";

const props = defineProps<{ rom: DetailedRomSchema }>();

const { t } = useI18n();
const platformsStore = storePlatforms();
const { filteredPlatforms } = storeToRefs(platformsStore);
const snackbar = useSnackbar();
const heartbeat = storeHeartbeat();
const scanningStore = storeScanning();
const uploadStore = storeUpload();

const supportedPatchExtensions = [
  ".ips",
  ".ups",
  ".bps",
  ".ppf",
  ".rup",
  ".aps",
  ".bdf",
  ".pmsr",
  ".vcdiff",
];

function getExt(name: string) {
  const match = name.match(/\.[^.]+$/);
  return match ? match[0].toLowerCase() : "";
}

function isPatchFile(file: RomFileSchema) {
  return (
    file.category === "patch" ||
    supportedPatchExtensions.includes(getExt(file.file_name))
  );
}

const selectedRomFile = ref<RomFileSchema | null>(null);
const selectedPatchFile = ref<RomFileSchema | null>(null);

const downloadLocally = ref(true);
// Uploading the patched ROM back into RomM needs write access. Viewers
// can only download locally, so both toggles are hidden for them and
// `saveIntoRomM` stays off — the apply button then reads "apply and
// download".
const canUpload = useCan("rom.upload");
const saveIntoRomM = ref(false);
// `selectedPlatformId` is the source of truth (matches PlatformSelect's
// id-keyed v-model); `selectedPlatform` is a derived lookup that keeps
// the rest of the file working against the full `Platform` object.
const selectedPlatformId = ref<number | null>(null);
const selectedPlatform = computed<Platform | null>(() => {
  if (selectedPlatformId.value === null) return null;
  return (
    filteredPlatforms.value.find((p) => p.id === selectedPlatformId.value) ??
    null
  );
});
const customFileName = ref("");

const applying = ref(false);
const loadError = ref<string | null>(null);
const statusMessage = ref<string | null>(null);

const baseFiles = computed(() =>
  props.rom.files.filter((f) => f.category === "game"),
);
const patchFiles = computed(() => props.rom.files.filter(isPatchFile));

const romExtension = computed(() =>
  selectedRomFile.value ? getExt(selectedRomFile.value.file_name) : "",
);

const filenamePlaceholder = computed(() => {
  if (selectedRomFile.value && selectedPatchFile.value) {
    const romBase = selectedRomFile.value.file_name.replace(/\.[^.]+$/, "");
    const patchBase = selectedPatchFile.value.file_name.replace(/\.[^.]+$/, "");
    return `${romBase} (patched-${patchBase})`;
  }
  return "";
});

// Auto-select when there's no ambiguity: a single base file / single
// patch file needs no picker. Reset on ROM change so switching to a
// different ROM doesn't keep a stale selection.
watch(
  () => props.rom,
  () => {
    selectedRomFile.value =
      baseFiles.value.length === 1 ? baseFiles.value[0] : null;
    selectedPatchFile.value =
      patchFiles.value.length === 1 ? patchFiles.value[0] : null;
  },
  { immediate: true },
);

async function readErrorDetail(err: unknown): Promise<string> {
  const anyErr = err as { response?: { data?: unknown }; message?: string };
  const data = anyErr?.response?.data;
  // Blob endpoints surface FastAPI's `{detail}` JSON as a Blob body.
  if (data instanceof Blob) {
    try {
      const parsed = JSON.parse(await data.text());
      if (parsed?.detail) return parsed.detail;
    } catch {
      /* fallthrough */
    }
  }
  if (
    data &&
    typeof data === "object" &&
    "detail" in data &&
    typeof (data as { detail: unknown }).detail === "string"
  ) {
    return (data as { detail: string }).detail;
  }
  return anyErr?.message ?? String(err);
}

async function patchRom() {
  loadError.value = null;
  statusMessage.value = null;

  if (!selectedRomFile.value)
    return (loadError.value = t("patcher.error-no-rom"));
  if (!selectedPatchFile.value) {
    return (loadError.value = t("patcher.error-no-patch"));
  }
  if (saveIntoRomM.value && !selectedPlatform.value) {
    return (loadError.value = t("patcher.error-no-platform"));
  }
  if (!downloadLocally.value && !saveIntoRomM.value) {
    return (loadError.value = t("patcher.error-no-action"));
  }

  applying.value = true;
  try {
    statusMessage.value = t("patcher.status-patching");

    const customBase = (
      customFileName.value || filenamePlaceholder.value
    ).trim();
    const outputFileName = customBase + romExtension.value;

    const response = await api.post(
      `/roms/${selectedRomFile.value.id}/patch`,
      {
        patch_file_id: selectedPatchFile.value.id,
        output_file_name: customFileName.value || undefined,
      },
      { responseType: "blob" },
    );

    const blob = response.data as Blob;
    const actions: string[] = [];

    // Backend reports whether the patch's source checksum matched the ROM.
    if (response.headers["x-patch-validated"] === "false") {
      snackbar.warning(t("patcher.validation-warning"), {
        icon: "mdi-alert",
        timeout: 6000,
      });
    }

    if (downloadLocally.value) {
      statusMessage.value = t("patcher.status-downloading");
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = outputFileName;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      actions.push(t("patcher.success-downloaded"));
    }

    if (saveIntoRomM.value && selectedPlatform.value) {
      statusMessage.value = t("patcher.status-uploading");
      const file = new File([blob], outputFileName, {
        type: "application/octet-stream",
      });
      await uploadPatchedFile(file, selectedPlatform.value.id);
      actions.push(t("patcher.success-uploaded"));
    }

    if (actions.length > 0) {
      statusMessage.value = t("patcher.success-message", {
        actions: actions.join(` ${t("common.and")} `),
      });
      setTimeout(() => {
        statusMessage.value = null;
      }, 3000);
    }
  } catch (err: unknown) {
    loadError.value = await readErrorDetail(err);
    statusMessage.value = null;
  } finally {
    applying.value = false;
  }
}

async function uploadPatchedFile(file: File, platformId: number) {
  const responses = await romApi.uploadRoms({
    filesToUpload: [file],
    platformId,
  });
  const failed = responses.filter((r) => r.status === "rejected");
  const successful = responses.filter((r) => r.status === "fulfilled");

  if (successful.length === 0) {
    const firstFailure = failed[0] as PromiseRejectedResult | undefined;
    const detail =
      firstFailure?.reason?.response?.data?.detail ||
      firstFailure?.reason?.message ||
      t("common.unknown-error");
    throw new Error(t("patcher.error-upload-failed", { error: detail }));
  }

  if (failed.length === 0) uploadStore.reset();

  snackbar.success(
    t("patcher.upload-success", {
      errors: failed.length > 0 ? t("patcher.upload-errors") : "",
    }),
    { icon: "mdi-check-bold", timeout: 3000 },
  );

  selectedPlatformId.value = null;
  saveIntoRomM.value = false;

  scanningStore.setScanning(true);
  if (!socket.connected) socket.connect();
  setTimeout(() => {
    socket.emit("scan", {
      platforms: [platformId],
      type: "quick",
      apis: heartbeat.getEnabledMetadataOptions().map((s) => s.value),
    });
  }, 2000);
}

const canApply = computed(
  () =>
    !!selectedRomFile.value &&
    !!selectedPatchFile.value &&
    !applying.value &&
    (downloadLocally.value || saveIntoRomM.value) &&
    (!saveIntoRomM.value || !!selectedPlatform.value),
);

const applyLabel = computed(() => {
  if (downloadLocally.value && saveIntoRomM.value) {
    return t("patcher.apply-download-upload");
  }
  if (saveIntoRomM.value) return t("patcher.apply-upload");
  return t("patcher.apply-download");
});
</script>

<template>
  <div class="r-v2-section-stack r-v2-patch">
    <p class="r-v2-patch__subtitle">
      {{ t("patcher.subtitle") }}
    </p>

    <div v-if="loadError || statusMessage" class="r-v2-patch__status">
      <RAlert v-if="loadError" type="error" density="compact">
        {{ loadError }}
      </RAlert>
      <RAlert v-if="statusMessage" type="info" density="compact">
        <template #prepend>
          <div class="r-v2-patch__status-spinner" />
        </template>
        {{ statusMessage }}
      </RAlert>
    </div>

    <!-- File pickers — base ROM + patch, combined into the output. The
         connector badge between them expresses that ROM + patch operation. -->
    <div class="r-v2-patch__flow">
      <!-- ROM panel -->
      <div class="r-v2-patch__panel">
        <div class="r-v2-patch__panel-label">
          <RIcon icon="mdi-disc" size="13" />
          {{ t("patcher.rom-file") }}
        </div>

        <div class="r-v2-patch__rom-info">
          <RPlatformIcon
            :slug="rom.platform_slug"
            :fs-slug="rom.platform_fs_slug"
            :name="rom.platform_display_name"
            :size="30"
            :show-tooltip="false"
          />
          <div class="r-v2-patch__rom-text">
            <span class="r-v2-patch__rom-name" :title="rom.fs_name">
              {{ rom.name ?? rom.fs_name }}
            </span>
            <span class="r-v2-patch__rom-file">
              {{ rom.fs_name }}
            </span>
          </div>
          <MissingFSBadge
            v-if="rom.missing_from_fs"
            :text="t('patcher.missing-from-fs')"
          />
        </div>

        <!-- More than one base file: pick which one to patch. -->
        <RSelect
          v-if="baseFiles.length > 1"
          v-model="selectedRomFile"
          :items="baseFiles"
          item-title="file_name"
          item-value="id"
          return-object
          :label="t('patcher.select-file')"
          variant="outlined"
          density="comfortable"
          hide-details
        >
          <template #item="{ props: itemProps, item }">
            <li v-bind="itemProps" class="r-v2-patch__file-row">
              <span class="r-select__item-title">{{ item.raw.file_name }}</span>
              <span class="r-v2-patch__file-size">
                {{ formatBytes(item.raw.file_size_bytes) }}
              </span>
            </li>
          </template>
        </RSelect>

        <!-- Exactly one base file: show it, no picker needed. -->
        <div v-else-if="selectedRomFile" class="r-v2-patch__file-single">
          <span
            class="r-v2-patch__file-name"
            :title="selectedRomFile.file_name"
          >
            {{ selectedRomFile.file_name }}
          </span>
          <span class="r-v2-patch__chip">
            <RIcon icon="mdi-weight" size="11" />
            {{ formatBytes(selectedRomFile.file_size_bytes) }}
          </span>
        </div>

        <p v-if="baseFiles.length === 0" class="r-v2-patch__warn">
          {{ t("patcher.no-files") }}
        </p>
      </div>

      <div class="r-v2-patch__connector" aria-hidden="true">
        <RIcon icon="mdi-plus" size="16" />
      </div>

      <!-- Patch panel -->
      <div class="r-v2-patch__panel">
        <div class="r-v2-patch__panel-head">
          <div class="r-v2-patch__panel-label">
            <RIcon icon="mdi-puzzle-outline" size="13" />
            {{ t("patcher.patch-file") }}
          </div>
          <!-- Supported formats live in a compact pill. `open-on-tap` so the
               tip reveals on hover (mouse) AND on tap (touch), not only on
               hover. -->
          <RTooltip location="bottom end" :offset="8" open-on-tap>
            <template #activator="{ props: tooltipProps }">
              <button
                v-bind="tooltipProps"
                type="button"
                class="r-v2-patch__formats-pill"
              >
                {{ t("patcher.supported-formats") }}
                <RIcon icon="mdi-information-outline" size="13" />
              </button>
            </template>
            <div class="r-v2-patch__formats-list">
              <span
                v-for="format in supportedPatchExtensions"
                :key="format"
                class="r-v2-patch__format-chip"
              >
                {{ format }}
              </span>
            </div>
          </RTooltip>
        </div>

        <!-- More than one patch file: pick which one to apply. -->
        <RSelect
          v-if="patchFiles.length > 1"
          v-model="selectedPatchFile"
          :items="patchFiles"
          item-title="file_name"
          item-value="id"
          return-object
          :label="t('patcher.select-patch-file')"
          variant="outlined"
          density="comfortable"
          hide-details
        >
          <template #item="{ props: itemProps, item }">
            <li v-bind="itemProps" class="r-v2-patch__file-row">
              <span class="r-select__item-title">{{ item.raw.file_name }}</span>
              <span class="r-v2-patch__file-size">
                {{ formatBytes(item.raw.file_size_bytes) }}
              </span>
            </li>
          </template>
        </RSelect>

        <!-- Exactly one patch file: show it, no picker needed. -->
        <div v-else-if="selectedPatchFile" class="r-v2-patch__file-single">
          <span
            class="r-v2-patch__file-name"
            :title="selectedPatchFile.file_name"
          >
            {{ selectedPatchFile.file_name }}
          </span>
          <span class="r-v2-patch__chip">
            <RIcon icon="mdi-weight" size="11" />
            {{ formatBytes(selectedPatchFile.file_size_bytes) }}
          </span>
        </div>

        <p v-if="patchFiles.length === 0" class="r-v2-patch__warn">
          {{ t("patcher.no-patch-files") }}
        </p>
      </div>
    </div>

    <!-- Controls panel -->
    <div class="r-v2-patch__controls">
      <!-- Viewers can only download locally, so the choice (download vs.
           upload to RomM) is meaningless: hide both toggles and let the
           apply button read "apply and download". Editors/admins get the
           full pair. -->
      <div v-if="canUpload" class="r-v2-patch__toggle-row">
        <RCheckbox
          v-model="downloadLocally"
          :label="t('patcher.download-locally')"
          hide-details
        />
        <RCheckbox
          v-model="saveIntoRomM"
          :label="t('patcher.upload-to-romm')"
          hide-details
        />
      </div>

      <RExpandTransition>
        <PlatformSelect
          v-if="saveIntoRomM"
          v-model="selectedPlatformId"
          :items="filteredPlatforms"
          :label="t('common.platforms')"
          prepend-inner-icon="mdi-controller"
          density="comfortable"
          :icon-size="32"
          show-meta
          clearable
          hide-details
        />
      </RExpandTransition>

      <RTextField
        v-model="customFileName"
        prefix-label="stacked"
        :placeholder="filenamePlaceholder"
        :suffix="romExtension"
        density="compact"
        hide-details
        clearable
      >
        <template #prefix-label>
          <RIcon icon="mdi-file-edit-outline" size="14" />
          {{ t("patcher.output-filename") }}
        </template>
      </RTextField>

      <div class="r-v2-patch__apply-row">
        <RBtn
          size="large"
          variant="flat"
          color="primary"
          prepend-icon="mdi-file-cog"
          :disabled="!canApply"
          :loading="applying"
          @click="patchRom"
        >
          {{ applyLabel }}
        </RBtn>
      </div>
    </div>

    <div class="r-v2-patch__brand">
      <span>{{ t("patcher.powered-by") }}</span>
      <img src="/assets/patcherjs/patcherjs.png" alt="patcher.js" />
    </div>
  </div>
</template>

<style scoped>
.r-v2-patch__subtitle {
  margin: 0;
  color: var(--r-color-fg-secondary);
  font-size: var(--r-font-size-sm);
  max-width: 560px;
}

.r-v2-patch__status {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.r-v2-patch__status-spinner {
  width: 16px;
  height: 16px;
  border-radius: 50%;
  border: 2px solid var(--r-color-surface-hover);
  border-top-color: var(--r-color-brand-primary);
  animation: r-v2-patch-spin 0.8s linear infinite;
}
@keyframes r-v2-patch-spin {
  to {
    transform: rotate(360deg);
  }
}

/* Flow row — base ROM and patch panels sit side by side, joined by the
   connector "+". A muted, translucent frame wraps both so they read as one
   combined "ROM + patch" operation rather than two unrelated cards. Stacks
   on narrow screens. */
.r-v2-patch__flow {
  display: flex;
  align-items: stretch;
  gap: 8px;
  padding: 10px;
  border-radius: var(--r-radius-xl);
  background: color-mix(in srgb, var(--r-color-surface) 45%, transparent);
  border: 1px solid color-mix(in srgb, var(--r-color-border) 55%, transparent);
}

.r-v2-patch__panel {
  flex: 1 1 0;
  min-width: 0;
  background: var(--r-color-bg-elevated);
  border: 1px solid var(--r-color-border);
  border-radius: var(--r-radius-lg);
  backdrop-filter: blur(18px);
  -webkit-backdrop-filter: blur(18px);
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

/* The "+" bridging the two panels — just a muted glyph, no surface/border,
   so it reads as a relationship between the boxes and not as an action
   button sitting between them. */
.r-v2-patch__connector {
  flex: none;
  align-self: center;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 2px;
  color: var(--r-color-fg-muted);
}

.r-v2-patch__panel-label {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  /* Reserve the pill's height on every panel-label so the ROM panel's
     header (label only) matches the patch panel's (label + formats pill),
     keeping both panels visually aligned. */
  min-height: 26px;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  font-weight: var(--r-font-weight-semibold);
  color: var(--r-color-fg-secondary);
}

/* Panel header — the small uppercase label on the left, the supported-
   formats pill on the opposite (right) edge of the same top row. */
.r-v2-patch__panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

/* ROM identity row — platform icon + name/file + missing-fs badge. */
.r-v2-patch__rom-info {
  display: flex;
  align-items: center;
  gap: 10px;
}
.r-v2-patch__rom-text {
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.r-v2-patch__rom-name {
  font-size: 13px;
  font-weight: var(--r-font-weight-medium);
  color: var(--r-color-fg);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.r-v2-patch__rom-file {
  font-size: 11px;
  color: var(--r-color-fg-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* Single-file display (no picker) — name + size chip. */
.r-v2-patch__file-single {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.r-v2-patch__file-name {
  font-size: 13px;
  color: var(--r-color-fg);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 220px;
}

/* Menu row layout for the multi-file RSelect: name on the left, size
   pushed to the right. */
.r-v2-patch__file-row {
  display: flex;
  align-items: center;
  gap: 8px;
}
.r-v2-patch__file-size {
  margin-left: auto;
  font-size: 11px;
  color: var(--r-color-fg-muted);
}

.r-v2-patch__warn {
  margin: 0;
  font-size: 12px;
  color: var(--r-color-warning-fg);
}

.r-v2-patch__chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px;
  background: var(--r-color-surface);
  border: 1px solid var(--r-color-border);
  border-radius: var(--r-radius-pill);
  font-size: 11px;
  color: var(--r-color-fg-secondary);
}

.r-v2-patch__formats-pill {
  appearance: none;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 3px 6px 3px 10px;
  background: var(--r-color-surface);
  border: 1px solid var(--r-color-border);
  border-radius: var(--r-radius-pill);
  font-family: inherit;
  font-size: 11px;
  font-weight: var(--r-font-weight-medium);
  color: var(--r-color-fg-secondary);
  transition:
    background var(--r-motion-fast) var(--r-motion-ease-out),
    border-color var(--r-motion-fast) var(--r-motion-ease-out),
    color var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-v2-patch__formats-pill:hover {
  background: var(--r-color-surface-hover);
  border-color: var(--r-color-border-strong);
  color: var(--r-color-fg);
}

/* Tooltip body — the full format list, wrapping in a compact grid. The
   tooltip surface ships 5px vertical / 10px horizontal padding; add the
   missing 5px top/bottom here so the list sits evenly inset all round. */
.r-v2-patch__formats-list {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 6px;
  max-width: 220px;
  padding-block: 5px;
}
.r-v2-patch__format-chip {
  padding: 1px 7px;
  background: var(--r-color-surface);
  border: 1px solid var(--r-color-border);
  border-radius: var(--r-radius-sm);
  font-size: 10.5px;
  color: var(--r-color-fg-secondary);
  font-family: var(--r-font-family-mono, monospace);
}

.r-v2-patch__controls {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 18px;
  background: var(--r-color-bg-elevated);
  border: 1px solid var(--r-color-border);
  border-radius: var(--r-radius-lg);
  backdrop-filter: blur(18px);
  -webkit-backdrop-filter: blur(18px);
}

.r-v2-patch__toggle-row {
  display: flex;
  gap: 18px;
  flex-wrap: wrap;
}

.r-v2-patch__apply-row {
  display: flex;
  justify-content: flex-end;
  margin-top: 4px;
  padding-top: 14px;
  border-top: 1px solid var(--r-color-border);
}

.r-v2-patch__brand {
  display: inline-flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 4px;
  font-size: var(--r-font-size-xs);
  color: var(--r-color-fg-faint);
  font-style: italic;
}
.r-v2-patch__brand img {
  height: 28px;
  opacity: 0.8;
  border-radius: 2px;
}

html[data-bp~="xs"] .r-v2-patch__flow {
  flex-direction: column;
}
html[data-bp~="xs"] .r-v2-patch__apply-row > * {
  width: 100%;
}
html[data-bp~="xs"] .r-v2-patch__file-name {
  max-width: 160px;
}
</style>
