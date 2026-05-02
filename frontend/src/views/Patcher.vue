<script setup lang="ts">
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import { computed, inject, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import type { RomFileSchema } from "@/__generated__";
import MissingFromFSIcon from "@/components/common/MissingFromFSIcon.vue";
import PlatformIcon from "@/components/common/Platform/PlatformIcon.vue";
import api from "@/services/api";
import romApi from "@/services/api/rom";
import socket from "@/services/socket";
import storeHeartbeat from "@/stores/heartbeat";
import storePlatforms, { type Platform } from "@/stores/platforms";
import storeRoms from "@/stores/roms";
import storeScanning from "@/stores/scanning";
import storeUpload from "@/stores/upload";
import type { Events } from "@/types/emitter";
import { formatBytes } from "@/utils";

const { t } = useI18n();
const emitter = inject<Emitter<Events>>("emitter");
const platformsStore = storePlatforms();
const { filteredPlatforms } = storeToRefs(platformsStore);
const heartbeat = storeHeartbeat();
const romsStore = storeRoms();
const { currentRom } = storeToRefs(romsStore);
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
const saveIntoRomM = ref(false);
const selectedPlatform = ref<Platform | null>(null);
const customFileName = ref("");

const applying = ref(false);
const loadError = ref<string | null>(null);
const statusMessage = ref<string | null>(null);

const baseFiles = computed(() =>
  (currentRom.value?.files ?? []).filter((f) => f.category === "game"),
);
const patchFiles = computed(() =>
  (currentRom.value?.files ?? []).filter(isPatchFile),
);

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

watch(
  currentRom,
  (rom) => {
    selectedRomFile.value = null;
    selectedPatchFile.value = null;
    if (!rom) return;
    if (baseFiles.value.length === 1) {
      selectedRomFile.value = baseFiles.value[0];
    }
    if (patchFiles.value.length === 1) {
      selectedPatchFile.value = patchFiles.value[0];
    }
  },
  { immediate: true },
);

async function readErrorDetail(err: unknown): Promise<string> {
  const anyErr = err as {
    response?: { data?: unknown };
    message?: string;
  };
  const data = anyErr?.response?.data;
  if (data instanceof Blob) {
    try {
      const text = await data.text();
      const parsed = JSON.parse(text);
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
  return anyErr?.message || String(err);
}

async function patchRom() {
  loadError.value = null;
  statusMessage.value = null;

  if (!selectedRomFile.value) {
    loadError.value = t("patcher.error-no-rom");
    return;
  }
  if (!selectedPatchFile.value) {
    loadError.value = t("patcher.error-no-patch");
    return;
  }
  if (saveIntoRomM.value && !selectedPlatform.value) {
    loadError.value = t("patcher.error-no-platform");
    return;
  }
  if (!downloadLocally.value && !saveIntoRomM.value) {
    loadError.value = t("patcher.error-no-action");
    return;
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
      "Upload failed";
    throw new Error(t("patcher.error-upload-failed", { error: detail }));
  }

  if (failed.length === 0) uploadStore.reset();

  emitter?.emit("snackbarShow", {
    msg: t("patcher.upload-success", {
      errors: failed.length > 0 ? t("patcher.upload-errors") : "",
    }),
    icon: "mdi-check-bold",
    color: "green",
    timeout: 3000,
  });

  selectedPlatform.value = null;
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
</script>

<template>
  <v-row class="align-center justify-center scroll h-100 px-4" no-gutters>
    <v-col cols="12" sm="10" md="8" xl="6">
      <v-card class="pa-4 bg-background" elevation="0">
        <v-card-title class="pb-2 px-0">{{ t("patcher.title") }}</v-card-title>
        <v-card-subtitle class="pb-2 px-0 text-body-2">
          {{ t("patcher.subtitle") }}
        </v-card-subtitle>
        <v-divider class="mt-2 mb-4" />

        <v-card-text class="pa-0">
          <v-alert
            v-if="loadError"
            type="error"
            class="mb-4"
            density="compact"
            >{{ loadError }}</v-alert
          >

          <v-alert
            v-if="statusMessage"
            class="mb-4 bg-primary"
            density="compact"
          >
            <div class="d-flex align-center">
              <v-progress-circular
                indeterminate
                size="20"
                width="2"
                class="mr-3"
              />
              {{ statusMessage }}
            </div>
          </v-alert>

          <v-row dense>
            <v-col cols="12" md="6">
              <v-sheet class="pa-3" rounded="lg" border color="surface">
                <div class="text-subtitle-1 mb-3">
                  {{ t("patcher.rom-file") }}
                </div>

                <div
                  v-if="currentRom"
                  class="d-flex align-center flex-wrap mb-3"
                >
                  <PlatformIcon
                    :slug="currentRom.platform_slug"
                    :name="currentRom.platform_display_name"
                    :fs-slug="currentRom.platform_fs_slug"
                    :size="30"
                    class="mr-2"
                  />
                  <div class="d-flex flex-column">
                    <span class="text-body-2">
                      {{ currentRom.name ?? currentRom.fs_name }}
                    </span>
                    <span class="text-caption text-medium-emphasis">
                      {{ currentRom.fs_name }}
                    </span>
                  </div>
                  <MissingFromFSIcon
                    v-if="currentRom.missing_from_fs"
                    text="Missing from filesystem"
                    chip
                    chip-label
                    chip-density="compact"
                    class="ml-2"
                  />
                </div>

                <v-select
                  v-if="baseFiles.length > 1"
                  v-model="selectedRomFile"
                  :items="baseFiles"
                  :label="t('patcher.select-file')"
                  item-title="file_name"
                  return-object
                  variant="outlined"
                  density="comfortable"
                  hide-details
                >
                  <template #item="{ props, item }">
                    <v-list-item
                      v-bind="props"
                      :title="item.raw.file_name"
                      :subtitle="formatBytes(item.raw.file_size_bytes)"
                    />
                  </template>
                </v-select>

                <div
                  v-else-if="selectedRomFile"
                  class="d-flex align-center flex-wrap"
                >
                  <v-chip size="small" label class="mr-2 mb-1">
                    {{ selectedRomFile.file_name }}
                  </v-chip>
                  <span class="text-caption text-medium-emphasis">
                    {{ formatBytes(selectedRomFile.file_size_bytes) }}
                  </span>
                </div>

                <div
                  v-if="currentRom && baseFiles.length === 0"
                  class="text-body-2 text-warning"
                >
                  {{ t("patcher.no-files") }}
                </div>
              </v-sheet>
            </v-col>

            <v-col cols="12" md="6">
              <v-sheet class="pa-3" rounded="lg" border color="surface">
                <div class="text-subtitle-1 mb-3">
                  {{ t("patcher.patch-file") }}
                </div>

                <v-select
                  v-if="patchFiles.length > 1"
                  v-model="selectedPatchFile"
                  :items="patchFiles"
                  :label="t('patcher.select-patch-file')"
                  item-title="file_name"
                  return-object
                  variant="outlined"
                  density="comfortable"
                  hide-details
                >
                  <template #item="{ props, item }">
                    <v-list-item
                      v-bind="props"
                      :title="item.raw.file_name"
                      :subtitle="formatBytes(item.raw.file_size_bytes)"
                    />
                  </template>
                </v-select>

                <div
                  v-else-if="selectedPatchFile"
                  class="d-flex align-center flex-wrap"
                >
                  <v-chip size="small" label class="mr-2 mb-1">
                    {{ selectedPatchFile.file_name }}
                  </v-chip>
                  <span class="text-caption text-medium-emphasis">
                    {{ formatBytes(selectedPatchFile.file_size_bytes) }}
                  </span>
                </div>

                <div
                  v-if="currentRom && patchFiles.length === 0"
                  class="text-body-2 text-warning"
                >
                  {{ t("patcher.no-patch-files") }}
                </div>

                <div class="text-subtitle-2 text-medium-emphasis mt-4">
                  {{ t("patcher.supported-formats") }}<br />
                  <v-chip
                    v-for="format in supportedPatchExtensions"
                    :key="format"
                    size="x-small"
                    class="mr-1 mt-1"
                    label
                    >{{ format }}</v-chip
                  >
                </div>
              </v-sheet>
            </v-col>
          </v-row>

          <v-sheet class="pa-3 mt-4" rounded="lg" border color="surface">
            <div class="d-flex align-center justify-space-between">
              <v-switch
                v-model="downloadLocally"
                color="primary"
                inset
                hide-details
                :label="t('patcher.download-locally')"
              />
              <v-switch
                v-model="saveIntoRomM"
                color="primary"
                inset
                hide-details
                :label="t('patcher.upload-to-romm')"
              />
            </div>

            <v-expand-transition>
              <div v-if="saveIntoRomM" class="mt-4">
                <v-select
                  v-model="selectedPlatform"
                  :items="filteredPlatforms"
                  :menu-props="{ maxHeight: 650 }"
                  :label="t('common.platforms')"
                  :disabled="!saveIntoRomM"
                  item-title="name"
                  return-object
                  prepend-inner-icon="mdi-controller"
                  variant="outlined"
                  density="comfortable"
                  hide-details
                  clearable
                >
                  <template #item="{ props, item }">
                    <v-list-item
                      v-bind="props"
                      class="py-4"
                      :title="item.raw.name ?? ''"
                      :subtitle="item.raw.fs_slug"
                    >
                      <template #prepend>
                        <PlatformIcon
                          :key="item.raw.slug"
                          :size="35"
                          :slug="item.raw.slug"
                          :name="item.raw.name"
                          :fs-slug="item.raw.fs_slug"
                        />
                      </template>
                      <template #append>
                        <MissingFromFSIcon
                          v-if="item.raw.missing_from_fs"
                          text="Missing platform from filesystem"
                          chip
                          chip-label
                          chip-density="compact"
                          class="ml-2"
                        />
                        <v-chip class="ml-1" size="small" label>
                          {{ item.raw.rom_count }}
                        </v-chip>
                      </template>
                    </v-list-item>
                  </template>
                  <template #chip="{ item }">
                    <v-chip>
                      <PlatformIcon
                        :key="item.raw.slug"
                        :slug="item.raw.slug"
                        :name="item.raw.name"
                        :fs-slug="item.raw.fs_slug"
                        :size="20"
                      />
                      <div class="ml-1">
                        {{ item.raw.name }}
                      </div>
                    </v-chip>
                  </template>
                </v-select>
              </div>
            </v-expand-transition>

            <v-text-field
              v-model="customFileName"
              :placeholder="filenamePlaceholder"
              :suffix="romExtension"
              :label="t('patcher.output-filename')"
              variant="outlined"
              density="compact"
              hide-details
              class="mt-4"
              clearable
            />

            <div class="d-flex mt-4">
              <v-spacer />
              <v-btn
                class="bg-toplayer text-primary"
                :disabled="
                  !selectedRomFile ||
                  !selectedPatchFile ||
                  applying ||
                  (!downloadLocally && !saveIntoRomM) ||
                  (saveIntoRomM && !selectedPlatform)
                "
                :loading="applying"
                :variant="
                  !selectedRomFile ||
                  !selectedPatchFile ||
                  applying ||
                  (!downloadLocally && !saveIntoRomM) ||
                  (saveIntoRomM && !selectedPlatform)
                    ? 'plain'
                    : 'flat'
                "
                @click="patchRom"
              >
                {{
                  downloadLocally && saveIntoRomM
                    ? t("patcher.apply-download-upload")
                    : saveIntoRomM
                      ? t("patcher.apply-upload")
                      : t("patcher.apply-download")
                }}
              </v-btn>
            </div>
          </v-sheet>
        </v-card-text>
      </v-card>

      <v-row class="mb-8 px-4" no-gutters>
        <v-col class="text-right align-center">
          <span class="text-medium-emphasis text-caption font-italic mr-2">{{
            t("patcher.powered-by")
          }}</span>
          <v-avatar rounded="0">
            <v-img src="/assets/patcherjs/patcherjs.png" />
          </v-avatar>
        </v-col>
      </v-row>
    </v-col>
  </v-row>
</template>
