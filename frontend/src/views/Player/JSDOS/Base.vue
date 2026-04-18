<script setup lang="ts">
import { useLocalStorage } from "@vueuse/core";
import { nextTick, onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute } from "vue-router";
import RomListItem from "@/components/common/Game/ListItem.vue";
import { ROUTES } from "@/plugins/router";
import romApi from "@/services/api/rom";
import type { DetailedRom } from "@/stores/roms";
import type { JsDosCI } from "@/types/jsdos";
import { getDownloadPath } from "@/utils";

const { t } = useI18n();
const route = useRoute();
const rom = ref<DetailedRom | null>(null);
const gameRunning = ref(false);
const fullScreenOnPlay = useLocalStorage("emulation.fullScreenOnPlay", true);
const scriptLoaded = ref(false);
const dosCI = ref<JsDosCI | null>(null);
const savingState = ref(false);
const loadingState = ref(false);

function getSaveKey(romId: number): string {
  return `jsdos:savestate:${romId}`;
}

async function saveStateToIDB(romId: number, data: Uint8Array) {
  const db = await openDB();
  return new Promise<void>((resolve, reject) => {
    const tx = db.transaction("savestates", "readwrite");
    tx.objectStore("savestates").put({ id: romId, data, timestamp: Date.now() });
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

async function loadStateFromIDB(romId: number): Promise<Uint8Array | null> {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction("savestates", "readonly");
    const req = tx.objectStore("savestates").get(romId);
    req.onsuccess = () => resolve(req.result?.data ?? null);
    req.onerror = () => reject(req.error);
  });
}

function openDB(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open("jsdos-savestates", 1);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains("savestates")) {
        db.createObjectStore("savestates", { keyPath: "id" });
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

async function loadScript(src: string): Promise<void> {
  return new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = src;
    script.onload = () => resolve();
    script.onerror = () => reject(new Error(`Failed to load ${src}`));
    document.body.appendChild(script);
  });
}

async function loadStylesheet(href: string): Promise<void> {
  return new Promise((resolve, reject) => {
    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = href;
    link.onload = () => resolve();
    link.onerror = () => reject(new Error(`Failed to load ${href}`));
    document.head.appendChild(link);
  });
}

async function loadJsDos() {
  try {
    await Promise.all([
      loadStylesheet("/assets/jsdos/js-dos.css"),
      loadScript("/assets/jsdos/js-dos.js"),
    ]);
    scriptLoaded.value = true;
  } catch {
    try {
      await Promise.all([
        loadStylesheet("https://v8.js-dos.com/latest/js-dos.css"),
        loadScript("https://v8.js-dos.com/latest/js-dos.js"),
      ]);
      scriptLoaded.value = true;
    } catch (e) {
      console.error("Failed to load js-dos:", e);
    }
  }
}

function onPlay() {
  gameRunning.value = true;

  nextTick(async () => {
    if (!rom.value) return;

    const container = document.getElementById("dos");
    if (!container) return;

    // Find .conf file in rom files and load its content
    const confFile = rom.value.files?.find((f: { file_name: string }) =>
      f.file_name.toLowerCase().endsWith(".conf"),
    );
    let dosboxConf: string | undefined;
    if (confFile) {
      try {
        const confUrl = getDownloadPath({
          rom: rom.value,
          fileIDs: [confFile.id],
        });
        const response = await fetch(confUrl);
        dosboxConf = await response.text();
      } catch (e) {
        console.error("Failed to load dosbox conf:", e);
      }
    }

    await window.Dos(container, {
      url: getDownloadPath({ rom: rom.value }),
      ...(dosboxConf ? { dosboxConf } : {}),
      noSidebar: true,
      onEvent: (event: string, ci: JsDosCI) => {
        if (event === "ci-ready") {
          dosCI.value = ci;
        }
      },
      onExit: () => {
        gameRunning.value = false;
        dosCI.value = null;
      },
    });

    if (fullScreenOnPlay.value && document.fullscreenEnabled) {
      container.requestFullscreen?.();
    }
  });
}

async function onSaveState() {
  if (!dosCI.value || !rom.value) return;
  savingState.value = true;
  try {
    const data = await dosCI.value.persist();
    await saveStateToIDB(rom.value.id, data);
  } catch (e) {
    console.error("Failed to save state:", e);
  } finally {
    savingState.value = false;
  }
}

async function onLoadState() {
  if (!rom.value) return;
  loadingState.value = true;
  try {
    const data = await loadStateFromIDB(rom.value.id);
    if (!data) return;

    const container = document.getElementById("dos");
    if (!container) return;

    if (dosCI.value) {
      await dosCI.value.exit();
      dosCI.value = null;
    }

    container.innerHTML = "";
    gameRunning.value = true;

    const blob = new Blob([new Uint8Array(data)], { type: "application/octet-stream" });
    const url = URL.createObjectURL(blob);

    await window.Dos(container, {
      url,
      noSidebar: true,
      onEvent: (event: string, ci: JsDosCI) => {
        if (event === "ci-ready") {
          dosCI.value = ci;
        }
      },
      onExit: () => {
        gameRunning.value = false;
        dosCI.value = null;
        URL.revokeObjectURL(url);
      },
    });
  } catch (e) {
    console.error("Failed to load state:", e);
  } finally {
    loadingState.value = false;
  }
}

function onFullScreenChange() {
  fullScreenOnPlay.value = !fullScreenOnPlay.value;
}

async function onlyQuit() {
  if (dosCI.value) {
    await dosCI.value.exit();
    dosCI.value = null;
  }
  window.history.back();
}

onMounted(async () => {
  const romResponse = await romApi.getRom({
    romId: parseInt(route.params.rom as string),
  });
  rom.value = romResponse.data;

  if (rom.value) {
    document.title = `${rom.value.name} | Play`;
  }

  await loadJsDos();
});
</script>

<template>
  <v-row v-if="rom" class="align-center justify-center scroll h-100" no-gutters>
    <v-col
      v-if="gameRunning"
      id="game-wrapper"
      cols="12"
      md="8"
      xl="10"
      class="bg-surface"
      rounded
    >
      <div id="dos" />
    </v-col>

    <v-col
      cols="12"
      :sm="!gameRunning ? 10 : 10"
      :md="!gameRunning ? 8 : 4"
      :xl="!gameRunning ? 6 : 2"
    >
      <v-row no-gutters>
        <v-col class="text-center">
          <v-icon size="x-large" color="primary">mdi-monitor</v-icon>
          <div class="text-h6 mt-2">js-dos</div>
        </v-col>
      </v-row>

      <v-divider class="my-4" />

      <v-row class="mb-4" no-gutters>
        <v-col>
          <RomListItem :rom="rom" with-filename with-size />
        </v-col>
      </v-row>

      <v-row class="px-3 text-center" no-gutters>
        <v-col>
          <v-row class="align-center ga-4" no-gutters>
            <v-col>
              <v-btn
                block
                size="large"
                :disabled="gameRunning"
                :variant="fullScreenOnPlay ? 'flat' : 'outlined'"
                :color="fullScreenOnPlay ? 'primary' : ''"
                @click="onFullScreenChange"
              >
                <v-icon class="mr-1">
                  {{
                    fullScreenOnPlay
                      ? "mdi-checkbox-outline"
                      : "mdi-checkbox-blank-outline"
                  }} </v-icon
                >{{ t("play.full-screen") }}
              </v-btn>
            </v-col>
            <v-col
              cols="12"
              :sm="gameRunning ? 12 : 7"
              :xl="gameRunning ? 12 : 9"
            >
              <v-btn
                color="primary"
                block
                :disabled="gameRunning || !scriptLoaded"
                variant="outlined"
                size="large"
                prepend-icon="mdi-play"
                @click="onPlay"
              >
                {{ t("play.play") }}
              </v-btn>
            </v-col>
          </v-row>

          <!-- Save / Load State buttons (visible when game is running) -->
          <v-row v-if="gameRunning" class="align-center ga-4 mt-4" no-gutters>
            <v-col>
              <v-btn
                block
                variant="outlined"
                size="large"
                :loading="savingState"
                :disabled="!dosCI || loadingState"
                prepend-icon="mdi-content-save"
                @click="onSaveState"
              >
                {{ t("play.save-state") }}
              </v-btn>
            </v-col>
            <v-col>
              <v-btn
                block
                variant="outlined"
                size="large"
                :loading="loadingState"
                :disabled="savingState"
                prepend-icon="mdi-folder-open"
                @click="onLoadState"
              >
                {{ t("play.load-state") }}
              </v-btn>
            </v-col>
          </v-row>

          <v-row v-if="!gameRunning" class="align-center ga-4 mt-4" no-gutters>
            <v-btn
              block
              variant="outlined"
              size="large"
              prepend-icon="mdi-arrow-left"
              @click="
                $router.push({
                  name: ROUTES.ROM,
                  params: { rom: rom?.id },
                })
              "
            >
              {{ t("play.back-to-game-details") }}
            </v-btn>
            <v-btn
              block
              variant="outlined"
              size="large"
              prepend-icon="mdi-arrow-left"
              @click="
                $router.push({
                  name: ROUTES.PLATFORM,
                  params: { platform: rom?.platform_id },
                })
              "
            >
              {{ t("play.back-to-gallery") }}
            </v-btn>
          </v-row>
          <v-btn
            v-if="gameRunning"
            class="mt-4"
            block
            variant="outlined"
            size="large"
            prepend-icon="mdi-exit-to-app"
            @click="onlyQuit"
          >
            {{ t("play.quit") }}
          </v-btn>
        </v-col>
      </v-row>
    </v-col>
  </v-row>
</template>

<style scoped>
#game-wrapper {
  height: 100%;
}

#dos {
  height: 100%;
  width: 100%;
}

@media (max-width: 960px) {
  #game-wrapper {
    height: calc(100vh - 55px);
  }
}
</style>
