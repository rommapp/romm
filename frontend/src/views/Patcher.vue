<script setup lang="ts">
import { useDropZone } from "@vueuse/core";
import { ref, onMounted } from "vue";
import { formatBytes } from "@/utils";

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

const supportedRomFormats = [
  ".nes",
  ".sfc",
  ".smc",
  ".fig",
  ".gb",
  ".gbc",
  ".gba",
  ".n64",
  ".z64",
  ".bin",
  ".fds",
  ".lnx",
  ".rom",
  ".img",
  ".iso",
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

    patched.save();
  } catch (err: any) {
    loadError.value = err?.message || String(err);
  } finally {
    applying.value = false;
  }
}

onMounted(async () => {
  // Preload core for faster interaction
  await ensureCoreLoaded();
});

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
</script>

<template>
  <v-row class="align-center justify-center scroll h-100 px-4" no-gutters>
    <v-col cols="12" sm="10" md="8" xl="6">
      <v-card class="pa-4 bg-background" elevation="0">
        <v-card-title class="pb-2">
          <v-row no-gutters>
            <v-col cols="auto">
              <v-img
                width="40"
                src="/assets/patcherjs/assets/patcherjs.png"
                class="mr-4"
              />
            </v-col>
            <v-col>
              <span>ROM Patcher</span>
            </v-col>
          </v-row>
        </v-card-title>
        <v-card-subtitle class="pb-2 text-body-2">
          Choose a base ROM and a patch file, then apply to download the patched
          ROM.
        </v-card-subtitle>
        <v-divider class="mb-4" />

        <v-card-text class="pb-0">
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
                <div class="text-subtitle-2">ROM file</div>
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
                  :accept="
                    supportedRomFormats.map((format) => '.' + format).join(',')
                  "
                  class="sr-only"
                  style="display: none"
                  @change="onRomChange"
                />
                <div class="text-caption text-medium-emphasis mt-4">
                  Supported rom formats<br />
                  <v-chip
                    v-for="format in supportedRomFormats"
                    size="x-small"
                    class="mr-1 mt-1"
                    label
                    >{{ format }}</v-chip
                  >
                </div>
              </v-sheet>
            </v-col>

            <v-col cols="12" md="6">
              <v-sheet class="pa-3" rounded="lg" border color="surface">
                <div class="text-subtitle-2">Patch file</div>
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
                  :accept="
                    supportedPatchFormats
                      .map((format) => '.' + format)
                      .join(',')
                  "
                  class="sr-only"
                  style="display: none"
                  @change="onPatchChange"
                />
                <div class="text-caption text-medium-emphasis mt-4">
                  Supported patch formats<br />
                  <v-chip
                    v-for="format in supportedPatchFormats"
                    size="x-small"
                    class="mr-1 mt-1"
                    label
                    >{{ format }}</v-chip
                  >
                </div>
              </v-sheet>
            </v-col>
          </v-row>

          <div class="d-flex align-right justify-space-left mt-4 mb-1">
            <v-spacer />
            <v-btn
              class="bg-toplayer text-primary"
              :disabled="!romFile || !patchFile || applying"
              :loading="applying"
              :variant="
                !romFile || !patchFile || applying == null ? 'plain' : 'flat'
              "
              @click="patchRom"
            >
              Apply patch
            </v-btn>
          </div>
        </v-card-text>
      </v-card>
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
