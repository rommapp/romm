<script setup lang="ts">
import { ref, onMounted } from "vue";

// Declare globals provided by local scripts
declare const BinFile: any;
declare const RomPatcher: any;

const loadError = ref<string | null>(null);
const coreLoaded = ref(false);

const romFile = ref<File | null>(null);
const patchFile = ref<File | null>(null);

const romBin = ref<any | null>(null);
const patchBin = ref<any | null>(null);

const applying = ref(false);

// Local asset URLs for patcher core (Vite will copy these assets)
const CORE_SCRIPTS = [
  new URL("../../assets/patcherjs/modules/HashCalculator.js", import.meta.url)
    .href,
  new URL("../../assets/patcherjs/modules/BinFile.js", import.meta.url).href,
  new URL(
    "../../assets/patcherjs/modules/RomPatcher.format.ips.js",
    import.meta.url,
  ).href,
  new URL(
    "../../assets/patcherjs/modules/RomPatcher.format.ups.js",
    import.meta.url,
  ).href,
  new URL(
    "../../assets/patcherjs/modules/RomPatcher.format.aps_n64.js",
    import.meta.url,
  ).href,
  new URL(
    "../../assets/patcherjs/modules/RomPatcher.format.aps_gba.js",
    import.meta.url,
  ).href,
  new URL(
    "../../assets/patcherjs/modules/RomPatcher.format.bps.js",
    import.meta.url,
  ).href,
  new URL(
    "../../assets/patcherjs/modules/RomPatcher.format.rup.js",
    import.meta.url,
  ).href,
  new URL(
    "../../assets/patcherjs/modules/RomPatcher.format.ppf.js",
    import.meta.url,
  ).href,
  new URL(
    "../../assets/patcherjs/modules/RomPatcher.format.bdf.js",
    import.meta.url,
  ).href,
  new URL(
    "../../assets/patcherjs/modules/RomPatcher.format.pmsr.js",
    import.meta.url,
  ).href,
  new URL(
    "../../assets/patcherjs/modules/RomPatcher.format.vcdiff.js",
    import.meta.url,
  ).href,
  new URL("../../assets/patcherjs/RomPatcher.js", import.meta.url).href,
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

function onRomChange(e: Event) {
  const input = e.target as HTMLInputElement;
  const f = input.files?.[0] || null;
  romFile.value = f;
  romBin.value = null;
}
function onPatchChange(e: Event) {
  const input = e.target as HTMLInputElement;
  const f = input.files?.[0] || null;
  patchFile.value = f;
  patchBin.value = null;
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
</script>

<template>
  <v-row class="align-center justify-center scroll h-100" no-gutters>
    <v-col cols="12" sm="10" md="8" xl="6">
      <v-card class="pa-4" elevation="2">
        <v-card-title class="pb-2">ROM Patcher</v-card-title>
        <v-card-text>
          <v-alert
            v-if="loadError"
            type="error"
            class="mb-4"
            density="compact"
            >{{ loadError }}</v-alert
          >

          <div class="d-flex align-center mb-3">
            <div class="mr-3">ROM file:</div>
            <input type="file" @change="onRomChange" />
          </div>

          <div class="d-flex align-center mb-4">
            <div class="mr-3">Patch file:</div>
            <input type="file" @change="onPatchChange" />
          </div>

          <v-btn :loading="applying" color="success" @click="patchRom"
            >Apply patch</v-btn
          >
        </v-card-text>
      </v-card>
    </v-col>
  </v-row>
</template>
