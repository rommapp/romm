<script setup lang="ts">
// Patcher — v2 shell around the same rom-patcher-js + web-worker pipeline
// as v1. The worker contract, the dynamic imports of `rom-patcher/*`
// modules, and the window.* globals are ported verbatim so that patching
// behaviour stays identical; only the chrome is v2.
import {
  RAlert,
  RBtn,
  RCheckbox,
  RDropzone,
  RExpandTransition,
  RIcon,
  RTextField,
} from "@v2/lib";
import { storeToRefs } from "pinia";
import { computed, onMounted, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import romApi from "@/services/api/rom";
import socket from "@/services/socket";
import storeHeartbeat from "@/stores/heartbeat";
import { type Platform } from "@/stores/platforms";
import storePlatforms from "@/stores/platforms";
import storeScanning from "@/stores/scanning";
import storeUpload from "@/stores/upload";
import { formatBytes } from "@/utils";
import PlatformSelect from "@/v2/components/shared/PlatformSelect.vue";
import { useSnackbar } from "@/v2/composables/useSnackbar";

/* eslint-disable @typescript-eslint/no-explicit-any */
declare global {
  interface Window {
    BinFile: any;
    IPS: any;
    UPS: any;
    APS: any;
    APSGBA: any;
    BPS: any;
    RUP: any;
    PPF: any;
    BDF: any;
    PMSR: any;
    VCDIFF: any;
  }
}
/* eslint-enable @typescript-eslint/no-explicit-any */

const { t } = useI18n();
const platformsStore = storePlatforms();
const { filteredPlatforms } = storeToRefs(platformsStore);
const loadError = ref<string | null>(null);
const coreLoaded = ref(false);
const romFile = ref<File | null>(null);
const patchFile = ref<File | null>(null);
const romDz = ref<InstanceType<typeof RDropzone> | null>(null);
const patchDz = ref<InstanceType<typeof RDropzone> | null>(null);
const applying = ref(false);
const statusMessage = ref<string | null>(null);
const downloadLocally = ref(true);
const saveIntoRomM = ref(true);
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
const filenamePlaceholder = ref("");
const snackbar = useSnackbar();
const heartbeat = storeHeartbeat();
const scanningStore = storeScanning();
const uploadStore = storeUpload();

const supportedPatchFormats = [
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

const romExtension = computed(() => {
  if (!romFile.value) return "";
  const match = romFile.value.name.match(/\.[^.]+$/);
  return match ? match[0] : "";
});

watch([romFile, patchFile], ([rom, patch]) => {
  if (rom && patch) {
    const romBaseName = rom.name.replace(/\.[^.]+$/, "");
    const patchNameWithoutExt = patch.name.replace(/\.[^.]+$/, "");
    filenamePlaceholder.value = `${romBaseName} (patched-${patchNameWithoutExt})`;
  } else {
    filenamePlaceholder.value = "";
  }
});

// Core loader — verbatim from v1 so all 9 patch formats are available.
async function ensureCoreLoaded() {
  if (coreLoaded.value) return;
  try {
    window.BinFile =
      window.IPS =
      window.UPS =
      window.APS =
      window.APSGBA =
      window.BPS =
      window.RUP =
      window.PPF =
      window.BDF =
      window.PMSR =
      window.VCDIFF =
        null;

    await Promise.all([
      import("rom-patcher/rom-patcher-js/modules/BinFile.js"),
      import("rom-patcher/rom-patcher-js/modules/HashCalculator.js"),
      import("rom-patcher/rom-patcher-js/modules/RomPatcher.format.aps_gba.js"),
      import("rom-patcher/rom-patcher-js/modules/RomPatcher.format.aps_n64.js"),
      import("rom-patcher/rom-patcher-js/modules/RomPatcher.format.bdf.js"),
      import("rom-patcher/rom-patcher-js/modules/RomPatcher.format.bps.js"),
      import("rom-patcher/rom-patcher-js/modules/RomPatcher.format.ips.js"),
      import("rom-patcher/rom-patcher-js/modules/RomPatcher.format.pmsr.js"),
      import("rom-patcher/rom-patcher-js/modules/RomPatcher.format.ppf.js"),
      import("rom-patcher/rom-patcher-js/modules/RomPatcher.format.rup.js"),
      import("rom-patcher/rom-patcher-js/modules/RomPatcher.format.ups.js"),
      import("rom-patcher/rom-patcher-js/modules/RomPatcher.format.vcdiff.js"),
      import("rom-patcher/rom-patcher-js/RomPatcher.js"),
    ]);

    coreLoaded.value = true;
  } catch (e: unknown) {
    loadError.value = (e as Error)?.message ?? String(e);
  }
}

function onRomInput(files: File[] | File | null) {
  const first = Array.isArray(files) ? (files[0] ?? null) : files;
  romFile.value = first ?? null;
}
function onPatchInput(files: File[] | File | null) {
  const first = Array.isArray(files) ? (files[0] ?? null) : files;
  patchFile.value = first ?? null;
}

async function patchRom() {
  loadError.value = null;
  statusMessage.value = null;
  if (!coreLoaded.value) await ensureCoreLoaded();
  if (!coreLoaded.value) return;

  if (!romFile.value) return (loadError.value = t("patcher.error-no-rom"));
  if (!patchFile.value) return (loadError.value = t("patcher.error-no-patch"));
  if (saveIntoRomM.value && !selectedPlatform.value) {
    return (loadError.value = t("patcher.error-no-platform"));
  }
  if (!downloadLocally.value && !saveIntoRomM.value) {
    return (loadError.value = t("patcher.error-no-action"));
  }

  applying.value = true;

  try {
    statusMessage.value = t("patcher.status-preparing");
    const romArrayBuffer = await romFile.value.arrayBuffer();
    const patchArrayBuffer = await patchFile.value.arrayBuffer();

    const worker = new Worker("/assets/patcherjs/patcher.worker.js");
    const patchedResult = await new Promise<{
      data: Uint8Array;
      fileName: string;
    }>((resolve, reject) => {
      worker.onmessage = (e) => {
        const { type, message, patchedData, fileName, error } = e.data;
        if (type === "STATUS") {
          statusMessage.value = message;
        } else if (type === "SUCCESS") {
          worker.terminate();
          resolve({ data: new Uint8Array(patchedData), fileName });
        } else if (type === "ERROR") {
          worker.terminate();
          reject(new Error(error));
        }
      };
      worker.onerror = (error) => {
        worker.terminate();
        reject(new Error(`Worker error: ${error.message}`));
      };
      worker.postMessage(
        {
          type: "PATCH",
          romData: romArrayBuffer,
          patchData: patchArrayBuffer,
          romFileName: romFile.value?.name,
          patchFileName: patchFile.value?.name,
          customFileName: customFileName.value || "",
        },
        [romArrayBuffer, patchArrayBuffer],
      );
    });

    const actions: string[] = [];

    if (downloadLocally.value) {
      statusMessage.value = t("patcher.status-downloading");
      const copy = new Uint8Array(patchedResult.data);
      const blob = new Blob([copy], { type: "application/octet-stream" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = patchedResult.fileName;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      actions.push(t("patcher.success-downloaded"));
    }

    if (saveIntoRomM.value && selectedPlatform.value) {
      statusMessage.value = t("patcher.status-uploading");
      await uploadPatchedRom(patchedResult.data, patchedResult.fileName);
      actions.push(t("patcher.success-uploaded"));
    }

    if (actions.length > 0) {
      statusMessage.value = t("patcher.success-message", {
        actions: actions.join(` ${t("common.and")} `),
      });
      setTimeout(() => {
        statusMessage.value = null;
      }, 3000);
    } else {
      statusMessage.value = null;
    }
  } catch (err: unknown) {
    loadError.value = (err as Error)?.message ?? String(err);
    statusMessage.value = null;
  } finally {
    applying.value = false;
  }
}

async function uploadPatchedRom(binaryData: Uint8Array, fileName: string) {
  if (!selectedPlatform.value) throw new Error(t("patcher.error-no-platform"));
  const platformId = selectedPlatform.value.id;

  const copy = new Uint8Array(binaryData);
  const file = new File([copy], fileName, { type: "application/octet-stream" });

  await romApi
    .uploadRoms({ filesToUpload: [file], platformId })
    .then((responses) => {
      const successfulUploads = responses.filter(
        (d) => d.status === "fulfilled",
      );
      const failedUploads = responses.filter((d) => d.status === "rejected");

      if (successfulUploads.length === 0) {
        const firstFailure = failedUploads[0] as PromiseRejectedResult;
        const errorDetail =
          firstFailure?.reason?.response?.data?.detail ||
          firstFailure?.reason?.message ||
          t("patcher.error-upload-failed", {
            error: t("common.unknown-error"),
          });
        console.error("Upload failed:", firstFailure);
        throw new Error(errorDetail);
      }

      if (failedUploads.length === 0) uploadStore.reset();

      snackbar.success(
        t("patcher.upload-success", {
          errors: failedUploads.length > 0 ? t("patcher.upload-errors") : "",
        }),
        { icon: "mdi-check-bold", timeout: 3000 },
      );

      romFile.value = null;
      patchFile.value = null;
      if (failedUploads.length === 0) {
        uploadStore.reset();
        romFile.value = null;
        patchFile.value = null;
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
    })
    .catch(({ response, message }) => {
      throw new Error(
        t("patcher.error-upload-failed", {
          error: response?.data?.detail || response?.statusText || message,
        }),
      );
    });
}

const canApply = computed(
  () =>
    !!romFile.value &&
    !!patchFile.value &&
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

onMounted(async () => {
  await ensureCoreLoaded();
});
</script>

<template>
  <div class="r-v2-section-stack">
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

    <!-- Dropzones -->
    <div class="r-v2-patch__panels">
      <!-- ROM dropzone -->
      <RDropzone
        ref="romDz"
        overlay
        class="r-v2-patch__zone"
        :release-label="t('patcher.drop-rom-here')"
        :input-label="t('patcher.choose-rom')"
        @files="onRomInput"
      >
        <div
          class="r-v2-patch__panel r-v2-patch__dropzone"
          :class="{ 'r-v2-patch__dropzone--filled': !!romFile }"
          role="button"
          tabindex="0"
          @click="romDz?.open()"
          @keydown.enter.prevent="romDz?.open()"
          @keydown.space.prevent="romDz?.open()"
        >
          <div class="r-v2-patch__panel-label">
            {{ t("patcher.rom-file") }}
          </div>
          <template v-if="!romFile">
            <div class="r-v2-patch__drop-empty">
              <RIcon icon="mdi-file-outline" size="40" color="primary" />
              <p class="r-v2-patch__drop-title">
                {{ t("patcher.drop-rom-here") }}
              </p>
              <p class="r-v2-patch__drop-hint">
                {{ t("patcher.drag-drop-rom") }}
              </p>
              <RBtn variant="outlined" color="primary" size="small">
                {{ t("patcher.choose-rom") }}
              </RBtn>
            </div>
          </template>
          <template v-else>
            <div class="r-v2-patch__drop-filled" @click.stop>
              <div class="r-v2-patch__drop-meta">
                <p class="r-v2-patch__drop-name" :title="romFile.name">
                  {{ romFile.name }}
                </p>
                <span class="r-v2-patch__chip">
                  <RIcon icon="mdi-weight" size="11" />
                  {{ formatBytes(romFile.size) }}
                </span>
              </div>
              <div class="r-v2-patch__drop-actions">
                <RBtn
                  variant="outlined"
                  color="primary"
                  size="small"
                  @click.stop="romDz?.open()"
                >
                  {{ t("patcher.replace") }}
                </RBtn>
                <button
                  type="button"
                  class="r-v2-patch__drop-clear"
                  :aria-label="t('common.clear')"
                  @click.stop="onRomInput(null)"
                >
                  <RIcon icon="mdi-close" size="14" />
                </button>
              </div>
            </div>
          </template>
        </div>
      </RDropzone>

      <!-- Patch dropzone -->
      <RDropzone
        ref="patchDz"
        overlay
        class="r-v2-patch__zone"
        :accept="supportedPatchFormats.join(',')"
        :release-label="t('patcher.drop-patch-here')"
        :input-label="t('patcher.choose-patch')"
        @files="onPatchInput"
      >
        <div
          class="r-v2-patch__panel r-v2-patch__dropzone"
          :class="{ 'r-v2-patch__dropzone--filled': !!patchFile }"
          role="button"
          tabindex="0"
          @click="patchDz?.open()"
          @keydown.enter.prevent="patchDz?.open()"
          @keydown.space.prevent="patchDz?.open()"
        >
          <div class="r-v2-patch__panel-label">
            {{ t("patcher.patch-file") }}
          </div>
          <template v-if="!patchFile">
            <div class="r-v2-patch__drop-empty">
              <RIcon icon="mdi-file-cog-outline" size="40" color="primary" />
              <p class="r-v2-patch__drop-title">
                {{ t("patcher.drop-patch-here") }}
              </p>
              <p class="r-v2-patch__drop-hint">
                {{ t("patcher.drag-drop-patch") }}
              </p>
              <RBtn variant="outlined" color="primary" size="small">
                {{ t("patcher.choose-patch") }}
              </RBtn>
            </div>
          </template>
          <template v-else>
            <div class="r-v2-patch__drop-filled" @click.stop>
              <div class="r-v2-patch__drop-meta">
                <p class="r-v2-patch__drop-name" :title="patchFile.name">
                  {{ patchFile.name }}
                </p>
                <span class="r-v2-patch__chip">
                  <RIcon icon="mdi-weight" size="11" />
                  {{ formatBytes(patchFile.size) }}
                </span>
              </div>
              <div class="r-v2-patch__drop-actions">
                <RBtn
                  variant="outlined"
                  color="primary"
                  size="small"
                  @click.stop="patchDz?.open()"
                >
                  {{ t("patcher.replace") }}
                </RBtn>
                <button
                  type="button"
                  class="r-v2-patch__drop-clear"
                  :aria-label="t('common.clear')"
                  @click.stop="onPatchInput(null)"
                >
                  <RIcon icon="mdi-close" size="14" />
                </button>
              </div>
            </div>
          </template>
          <div class="r-v2-patch__formats" @click.stop>
            <span class="r-v2-patch__formats-label">
              {{ t("patcher.supported-formats") }}
            </span>
            <span
              v-for="format in supportedPatchFormats"
              :key="format"
              class="r-v2-patch__format-chip"
            >
              {{ format }}
            </span>
          </div>
        </div>
      </RDropzone>
    </div>

    <!-- Controls panel -->
    <div class="r-v2-patch__controls">
      <div class="r-v2-patch__toggle-row">
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

.r-v2-patch__panels {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

/* RDropzone wrapper (overlay mode) — fills the grid cell so the inner
   panel stretches to the row height; anchors the drag-over overlay. */
.r-v2-patch__zone {
  display: flex;
}
.r-v2-patch__zone > .r-v2-patch__panel {
  flex: 1;
  min-width: 0;
}

.r-v2-patch__panel {
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

.r-v2-patch__panel-label {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  font-weight: var(--r-font-weight-semibold);
  color: var(--r-color-fg-secondary);
}

.r-v2-patch__dropzone {
  position: relative;
  cursor: pointer;
  border: 2px dashed
    color-mix(in srgb, var(--r-color-brand-primary) 25%, transparent);
  transition:
    border-color var(--r-motion-fast) var(--r-motion-ease-out),
    background var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-v2-patch__dropzone:hover {
  border-color: color-mix(
    in srgb,
    var(--r-color-brand-primary) 45%,
    transparent
  );
}
.r-v2-patch__dropzone--filled {
  border-style: solid;
  border-color: var(--r-color-border-strong);
  cursor: default;
}

.r-v2-patch__drop-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 24px 16px;
  color: var(--r-color-fg-secondary);
  text-align: center;
}
.r-v2-patch__drop-title {
  margin: 6px 0 0;
  font-size: 14px;
  font-weight: var(--r-font-weight-semibold);
  color: var(--r-color-fg);
}
.r-v2-patch__drop-hint {
  margin: 0 0 8px;
  font-size: 12px;
  color: var(--r-color-fg-muted);
}

.r-v2-patch__drop-filled {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 6px 4px;
}
.r-v2-patch__drop-meta {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
}
.r-v2-patch__drop-name {
  margin: 0;
  font-size: 13px;
  font-weight: var(--r-font-weight-medium);
  color: var(--r-color-fg);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 260px;
}
.r-v2-patch__drop-actions {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.r-v2-patch__drop-clear {
  appearance: none;
  border: 0;
  background: var(--r-color-surface);
  color: var(--r-color-fg-secondary);
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  cursor: pointer;
  transition: background var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-v2-patch__drop-clear:hover {
  background: color-mix(
    in srgb,
    var(--r-color-status-base-danger) 18%,
    transparent
  );
  color: var(--r-color-danger-fg);
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

.r-v2-patch__formats {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 6px;
  margin-top: 4px;
  cursor: default;
}
.r-v2-patch__formats-label {
  font-size: 11px;
  color: var(--r-color-fg-muted);
  text-transform: uppercase;
  letter-spacing: 0.04em;
  width: 100%;
  margin-bottom: 2px;
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

html[data-bp~="xs"] .r-v2-patch__panels {
  grid-template-columns: 1fr;
}
html[data-bp~="xs"] .r-v2-patch__drop-name {
  max-width: 160px;
}
</style>
