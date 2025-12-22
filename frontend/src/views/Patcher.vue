<script setup lang="ts">
import { useDropZone } from "@vueuse/core";
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import { inject, ref, onMounted } from "vue";
import { useI18n } from "vue-i18n";
import MissingFromFSIcon from "@/components/common/MissingFromFSIcon.vue";
import PlatformIcon from "@/components/common/Platform/PlatformIcon.vue";
import romApi from "@/services/api/rom";
import socket from "@/services/socket";
import storeHeartbeat from "@/stores/heartbeat";
import { type Platform } from "@/stores/platforms";
import storePlatforms from "@/stores/platforms";
import storeScanning from "@/stores/scanning";
import storeUpload from "@/stores/upload";
import type { Events } from "@/types/emitter";
import { formatBytes } from "@/utils";

const { t } = useI18n();
const platformsStore = storePlatforms();
const { filteredPlatforms } = storeToRefs(platformsStore);
// Declare globals provided by local scripts
declare const BinFile: any;
declare const RomPatcher: any;
const loadError = ref<string | null>(null);
const coreLoaded = ref(false);
const romFile = ref<File | null>(null);
const patchFile = ref<File | null>(null);
const romBin = ref<any | null>(null);
const patchBin = ref<any | null>(null);
const romDropZoneRef = ref<HTMLDivElement | null>(null);
const patchDropZoneRef = ref<HTMLDivElement | null>(null);
const romInputRef = ref<HTMLInputElement | null>(null);
const patchInputRef = ref<HTMLInputElement | null>(null);
const applying = ref(false);
const saveIntoRomM = ref(false);
const selectedPlatform = ref<Platform | null>(null);
const emitter = inject<Emitter<Events>>("emitter");
const heartbeat = storeHeartbeat();
const scanningStore = storeScanning();
const uploadStore = storeUpload();
// Load core scripts via absolute asset paths (mirrors emulator loader approach)
const PATCHER_BASE_PATH = "/assets/patcherjs";
const CORE_SCRIPTS = [
  `${PATCHER_BASE_PATH}/modules/HashCalculator.js`,
  `${PATCHER_BASE_PATH}/modules/BinFile.js`,
  `${PATCHER_BASE_PATH}/modules/RomPatcher.format.ips.js`,
  `${PATCHER_BASE_PATH}/modules/RomPatcher.format.ups.js`,
  `${PATCHER_BASE_PATH}/modules/RomPatcher.format.aps_n64.js`,
  `${PATCHER_BASE_PATH}/modules/RomPatcher.format.aps_gba.js`,
  `${PATCHER_BASE_PATH}/modules/RomPatcher.format.bps.js`,
  `${PATCHER_BASE_PATH}/modules/RomPatcher.format.rup.js`,
  `${PATCHER_BASE_PATH}/modules/RomPatcher.format.ppf.js`,
  `${PATCHER_BASE_PATH}/modules/RomPatcher.format.bdf.js`,
  `${PATCHER_BASE_PATH}/modules/RomPatcher.format.pmsr.js`,
  `${PATCHER_BASE_PATH}/modules/RomPatcher.format.vcdiff.js`,
  `${PATCHER_BASE_PATH}/RomPatcher.js`,
];
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
const { isOverDropZone: isOverRomDropZone } = useDropZone(romDropZoneRef, {
  onDrop: onRomDrop,
  multiple: false,
  preventDefaultForUnhandled: true,
});
const { isOverDropZone: isOverPatchDropZone } = useDropZone(patchDropZoneRef, {
  onDrop: onPatchDrop,
  multiple: false,
  preventDefaultForUnhandled: true,
});

function loadScriptSequentially(urls: string[]): Promise<void> {
  return new Promise((resolve, reject) => {
    let i = 0;
    const next = () => {
      if (i >= urls.length) {
        resolve();
        return;
      }
      const s = document.createElement("script");
      s.src = urls[i++];
      s.type = "text/javascript";
      s.onload = () => next();
      s.onerror = () => reject(new Error("Failed to load script: " + s.src));
      document.head.appendChild(s);
    };
    next();
  });
}

async function ensureCoreLoaded() {
  if (coreLoaded.value) return;
  try {
    await loadScriptSequentially(CORE_SCRIPTS);
    coreLoaded.value = true;
  } catch (e: any) {
    loadError.value = e?.message || String(e);
  }
}

function setRomFile(file: File | null) {
  romFile.value = file;
  romBin.value = null;
}

function setPatchFile(file: File | null) {
  patchFile.value = file;
  patchBin.value = null;
}

function onRomInput(files: File[] | File | null) {
  const first = Array.isArray(files) ? (files[0] ?? null) : files;
  setRomFile(first ?? null);
}

function onPatchInput(files: File[] | File | null) {
  const first = Array.isArray(files) ? (files[0] ?? null) : files;
  setPatchFile(first ?? null);
}

function onRomChange(e: Event) {
  const input = e.target as HTMLInputElement;
  onRomInput(input.files ? Array.from(input.files) : null);
  if (input) input.value = "";
}

function onPatchChange(e: Event) {
  const input = e.target as HTMLInputElement;
  onPatchInput(input.files ? Array.from(input.files) : null);
  if (input) input.value = "";
}

function onRomDrop(files: File[] | null) {
  onRomInput(files);
}

function onPatchDrop(files: File[] | null) {
  onPatchInput(files);
}

function triggerRomInput() {
  romInputRef.value?.click();
}

function triggerPatchInput() {
  patchInputRef.value?.click();
}

async function patchRom() {
  loadError.value = null;
  if (!coreLoaded.value) await ensureCoreLoaded();
  if (!coreLoaded.value) return; // bail on error

  if (!romFile.value) {
    loadError.value = "Please select a ROM file.";
    return;
  }
  if (!patchFile.value) {
    loadError.value = "Please select a patch file.";
    return;
  }

  if (saveIntoRomM.value && !selectedPlatform.value) {
    loadError.value = "Please select a platform to upload to.";
    return;
  }

  applying.value = true;
  try {
    // Build BinFile objects asynchronously
    await new Promise<void>((resolve, reject) => {
      try {
        new BinFile(romFile.value, (bf: any) => {
          romBin.value = bf;
          resolve();
        });
      } catch (err) {
        reject(err);
      }
    });
    await new Promise<void>((resolve, reject) => {
      try {
        new BinFile(patchFile.value, (bf: any) => {
          patchBin.value = bf;
          resolve();
        });
      } catch (err) {
        reject(err);
      }
    });

    if (!romBin.value || !patchBin.value) {
      throw new Error("Failed to read selected files.");
    }

    const patch = RomPatcher.parsePatchFile(patchBin.value);
    if (!patch) {
      throw new Error("Unsupported or invalid patch format.");
    }

    const patched = RomPatcher.applyPatch(romBin.value, patch, {
      requireValidation: false,
      fixChecksum: false,
      outputSuffix: true,
    });

    if (saveIntoRomM.value && selectedPlatform.value) {
      await uploadPatchedRom(patched);
    } else {
      patched.save();
    }
  } catch (err: any) {
    loadError.value = err?.message || String(err);
  } finally {
    applying.value = false;
  }
}

async function uploadPatchedRom(patchedBin: any) {
  if (!selectedPlatform.value) {
    throw new Error("No platform selected.");
  }
  const platformId = selectedPlatform.value.id;

  // Convert the patched BinFile to a File object
  // Try to get binary data from various possible properties
  let binaryData: Uint8Array | ArrayBuffer | null = null;
  if (patchedBin._u8array instanceof Uint8Array) {
    binaryData = patchedBin._u8array;
  } else if (patchedBin.u8array instanceof Uint8Array) {
    binaryData = patchedBin.u8array;
  } else if (patchedBin.fileContent instanceof Uint8Array) {
    binaryData = patchedBin.fileContent;
  } else if (patchedBin.fileContent instanceof ArrayBuffer) {
    binaryData = new Uint8Array(patchedBin.fileContent);
  } else if (patchedBin.data instanceof Uint8Array) {
    binaryData = patchedBin.data;
  } else if (patchedBin instanceof Uint8Array) {
    binaryData = patchedBin;
  } else if (patchedBin.bytes instanceof Uint8Array) {
    binaryData = patchedBin.bytes;
  }

  if (!binaryData) {
    console.error("Patched BinFile structure:", patchedBin);
    throw new Error("Unable to extract binary data from patched ROM");
  }

  // Ensure binaryData is a proper Uint8Array with ArrayBuffer backing
  const uint8array =
    binaryData instanceof Uint8Array
      ? new Uint8Array(binaryData)
      : new Uint8Array(binaryData);

  const blob = new Blob([uint8array], { type: "application/octet-stream" });
  const fileName = patchedBin.fileName || patchedBin.name || "patched_rom";
  const file = new File([blob], fileName, { type: "application/octet-stream" });

  // Upload the patched ROM
  await romApi
    .uploadRoms({
      filesToUpload: [file],
      platformId: platformId,
    })
    .then((responses: PromiseSettledResult<unknown>[]) => {
      const successfulUploads = responses.filter(
        (d) => d.status === "fulfilled",
      );
      const failedUploads = responses.filter((d) => d.status === "rejected");

      if (successfulUploads.length === 0) {
        // Get detailed error message from the first failed upload
        const firstFailure = failedUploads[0] as PromiseRejectedResult;
        const errorDetail =
          firstFailure?.reason?.response?.data?.detail ||
          firstFailure?.reason?.message ||
          "Upload failed with unknown error";
        console.error("Upload failed:", firstFailure);
        throw new Error(errorDetail);
      }

      if (failedUploads.length === 0) {
        uploadStore.reset();
      }

      emitter?.emit("snackbarShow", {
        msg: `Patched ROM uploaded successfully${
          failedUploads.length > 0 ? " (with some errors)" : ""
        }. Starting scan...`,
        icon: "mdi-check-bold",
        color: "green",
        timeout: 3000,
      });

      // Clear form after successful upload
      romFile.value = null;
      patchFile.value = null;
      romBin.value = null;
      patchBin.value = null;
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
    })
    .catch(({ response, message }) => {
      throw new Error(
        `Unable to upload ROM: ${
          response?.data?.detail || response?.statusText || message
        }`,
      );
    });
}

onMounted(async () => {
  // Preload core for faster interaction
  await ensureCoreLoaded();
});
</script>

<template>
  <v-row class="align-center justify-center scroll h-100 px-4" no-gutters>
    <v-col cols="12" sm="10" md="8" xl="6">
      <v-card class="pa-4 bg-background" elevation="0">
        <v-card-title class="pb-2 px-0">ROM Patcher</v-card-title>
        <v-card-subtitle class="pb-2 px-0 text-body-2">
          Choose a base ROM and a patch file, then apply to download the patched
          ROM.
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

          <v-row class="mb-2" dense>
            <v-col cols="12" md="6">
              <v-sheet class="pa-3" rounded="lg" border color="surface">
                <div class="text-subtitle-1">ROM file</div>
                <div
                  ref="romDropZoneRef"
                  class="dropzone-container rounded-lg transition-all duration-300 ease-in-out mt-4"
                  :class="{
                    'dropzone-active': isOverRomDropZone,
                    'dropzone-has-files': !!romFile,
                  }"
                  role="button"
                  tabindex="0"
                  @click="triggerRomInput"
                  @keydown.enter.prevent="triggerRomInput"
                  @keydown.space.prevent="triggerRomInput"
                >
                  <div
                    v-if="!romFile"
                    class="flex flex-col items-center justify-center h-full min-h-[180px] p-6 text-center transition-all duration-300 ease-in-out"
                  >
                    <v-icon
                      :class="{ 'animate-pulse-glow': isOverRomDropZone }"
                      size="40"
                      color="primary"
                    >
                      {{ isOverRomDropZone ? "mdi-file" : "mdi-file-outline" }}
                    </v-icon>
                    <div class="text-subtitle-2 mt-3 mb-1">Drop ROM here</div>
                    <p class="text-body-2 text-medium-emphasis mb-3">
                      Drag & drop a ROM file or click to browse.
                    </p>
                    <v-btn color="primary" variant="outlined" size="small">
                      Choose ROM
                    </v-btn>
                  </div>

                  <div
                    v-else
                    class="d-flex align-center justify-space-between h-full min-h-[120px] px-4"
                  >
                    <div>
                      <div class="text-subtitle-2">{{ romFile.name }}</div>
                      <div class="text-caption text-medium-emphasis">
                        <v-chip label>
                          {{ formatBytes(romFile.size) }}
                        </v-chip>
                      </div>
                    </div>
                    <div class="d-flex align-center">
                      <v-btn
                        color="primary"
                        variant="outlined"
                        size="small"
                        class="mr-2"
                        @click.stop="triggerRomInput"
                      >
                        Replace
                      </v-btn>
                      <v-btn
                        icon
                        variant="plain"
                        @click.stop="onRomInput(null)"
                      >
                        <v-icon color="red"> mdi-close </v-icon>
                      </v-btn>
                    </div>
                  </div>
                </div>
                <input
                  ref="romInputRef"
                  type="file"
                  class="sr-only"
                  style="display: none"
                  @change="onRomChange"
                />
              </v-sheet>
            </v-col>

            <v-col cols="12" md="6">
              <v-sheet class="pa-3" rounded="lg" border color="surface">
                <div class="text-subtitle-1">Patch file</div>
                <div
                  ref="patchDropZoneRef"
                  class="dropzone-container rounded-lg transition-all duration-300 ease-in-out mt-4"
                  :class="{
                    'dropzone-active': isOverPatchDropZone,
                    'dropzone-has-files': !!patchFile,
                  }"
                  role="button"
                  tabindex="0"
                  @click="triggerPatchInput"
                  @keydown.enter.prevent="triggerPatchInput"
                  @keydown.space.prevent="triggerPatchInput"
                >
                  <div
                    v-if="!patchFile"
                    class="flex flex-col items-center justify-center h-full min-h-[180px] p-6 text-center transition-all duration-300 ease-in-out"
                  >
                    <v-icon
                      :class="{ 'animate-pulse-glow': isOverPatchDropZone }"
                      size="40"
                      color="primary"
                    >
                      {{
                        isOverPatchDropZone
                          ? "mdi-file-cog"
                          : "mdi-file-cog-outline"
                      }}
                    </v-icon>
                    <div class="text-subtitle-2 mt-3 mb-1">Drop patch here</div>
                    <p class="text-body-2 text-medium-emphasis mb-3">
                      Drag & drop a patch file or click to browse.
                    </p>
                    <v-btn color="primary" variant="outlined" size="small">
                      Choose patch
                    </v-btn>
                  </div>

                  <div
                    v-else
                    class="d-flex align-center justify-space-between h-full min-h-[120px] px-4"
                  >
                    <div>
                      <div class="text-subtitle-2">{{ patchFile.name }}</div>
                      <div class="text-caption text-medium-emphasis">
                        <v-chip label>
                          {{ formatBytes(patchFile.size) }}
                        </v-chip>
                      </div>
                    </div>
                    <div class="d-flex align-center">
                      <v-btn
                        color="primary"
                        variant="outlined"
                        size="small"
                        class="mr-2"
                        @click.stop="triggerPatchInput"
                      >
                        Replace
                      </v-btn>
                      <v-btn
                        icon
                        variant="plain"
                        @click.stop="onPatchInput(null)"
                      >
                        <v-icon color="red"> mdi-close </v-icon>
                      </v-btn>
                    </div>
                  </div>
                </div>
                <input
                  ref="patchInputRef"
                  type="file"
                  :accept="supportedPatchFormats.join(',')"
                  class="sr-only"
                  style="display: none"
                  @change="onPatchChange"
                />
                <div class="text-subtitle-2 text-medium-emphasis mt-4">
                  Supported patch formats<br />
                  <v-chip
                    v-for="format in supportedPatchFormats"
                    size="small"
                    class="mr-1 mt-1"
                    label
                    >{{ format }}</v-chip
                  >
                </div>
              </v-sheet>
              <div class="d-flex align-center justify-space-left mt-4">
                <v-spacer />
                <v-switch
                  v-model="saveIntoRomM"
                  color="primary"
                  inset
                  hide-details
                  label="Upload patched rom to RomM"
                />
              </div>

              <v-expand-transition>
                <div
                  v-if="saveIntoRomM"
                  class="d-flex align-center justify-space-left mt-4"
                >
                  <v-spacer />
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
                          <v-row
                            v-if="item.raw.is_identified"
                            class="text-white text-shadow text-center"
                            no-gutters
                          >
                            <v-col cols="12">
                              <v-avatar
                                v-if="item.raw.igdb_id"
                                variant="text"
                                size="25"
                                rounded
                                class="mr-1"
                              >
                                <v-img src="/assets/scrappers/igdb.png" />
                              </v-avatar>

                              <v-avatar
                                v-if="item.raw.ss_id"
                                variant="text"
                                size="25"
                                rounded
                                class="mr-1"
                              >
                                <v-img src="/assets/scrappers/ss.png" />
                              </v-avatar>

                              <v-avatar
                                v-if="item.raw.moby_slug"
                                variant="text"
                                size="25"
                                rounded
                                class="mr-1"
                              >
                                <v-img src="/assets/scrappers/moby.png" />
                              </v-avatar>

                              <v-avatar
                                v-if="item.raw.ra_id"
                                variant="text"
                                size="25"
                                rounded
                                class="mr-1"
                              >
                                <v-img src="/assets/scrappers/ra.png" />
                              </v-avatar>

                              <v-avatar
                                v-if="item.raw.launchbox_id"
                                variant="text"
                                size="25"
                                rounded
                                class="mr-1"
                                style="background: #185a7c"
                              >
                                <v-img src="/assets/scrappers/launchbox.png" />
                              </v-avatar>

                              <v-avatar
                                v-if="item.raw.hasheous_id"
                                variant="text"
                                size="25"
                                rounded
                                class="mr-1"
                              >
                                <v-img src="/assets/scrappers/hasheous.png" />
                              </v-avatar>

                              <v-avatar
                                v-if="item.raw.flashpoint_id"
                                variant="text"
                                size="25"
                                rounded
                                class="mr-1"
                              >
                                <v-img src="/assets/scrappers/flashpoint.png" />
                              </v-avatar>

                              <v-avatar
                                v-if="item.raw.hltb_slug"
                                class="bg-surface"
                                variant="text"
                                size="25"
                                rounded
                              >
                                <v-img src="/assets/scrappers/hltb.png" />
                              </v-avatar>
                            </v-col>
                          </v-row>
                          <v-row
                            v-else
                            class="text-white text-shadow text-center"
                            no-gutters
                          >
                            <v-chip color="red" size="small" label>
                              <v-icon class="mr-1"> mdi-close </v-icon>
                              {{ t("scan.not-identified").toUpperCase() }}
                            </v-chip>
                          </v-row>
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

              <div class="d-flex align-right justify-space-left mt-8">
                <v-spacer />
                <v-btn
                  class="bg-toplayer text-primary"
                  :disabled="
                    !romFile ||
                    !patchFile ||
                    applying ||
                    (saveIntoRomM && !selectedPlatform)
                  "
                  :loading="applying"
                  :variant="
                    !romFile ||
                    !patchFile ||
                    applying == null ||
                    (saveIntoRomM && !selectedPlatform)
                      ? 'plain'
                      : 'flat'
                  "
                  @click="patchRom"
                >
                  {{ saveIntoRomM ? "Apply & Upload" : "Apply patch" }}
                </v-btn>
              </div>
            </v-col>
          </v-row>
        </v-card-text>
      </v-card>

      <v-row class="mb-8 px-4" no-gutters>
        <v-col class="text-right align-center">
          <span class="text-medium-emphasis text-caption font-italic mr-2"
            >Powered by patcherjs</span
          >
          <v-avatar rounded="0">
            <v-img src="/assets/patcherjs/assets/patcherjs.png" />
          </v-avatar>
        </v-col>
      </v-row>
    </v-col>
  </v-row>
</template>

<style scoped>
.dropzone-container {
  border: 2px dashed rgba(var(--v-theme-primary), 0.3);
}

.dropzone-container.dropzone-active {
  border: 2px dashed rgba(var(--v-theme-primary));
  background-color: rgba(var(--v-theme-primary), 0.05);
}

.dropzone-container.dropzone-has-files {
  border: none;
  background-color: rgba(var(--v-theme-surface), 0.5);
}

.animate-pulse-glow {
  animation: pulse-glow 1.5s ease-in-out infinite;
}

@keyframes pulse-glow {
  0% {
    transform: scale(1);
    filter: brightness(1) drop-shadow(0 0 0 rgba(var(--v-theme-primary), 0));
  }
  50% {
    transform: scale(1.1);
    filter: brightness(1.2)
      drop-shadow(0 0 20px rgba(var(--v-theme-primary), 0.6));
  }
  100% {
    transform: scale(1);
    filter: brightness(1) drop-shadow(0 0 0 rgba(var(--v-theme-primary), 0));
  }
}
</style>
