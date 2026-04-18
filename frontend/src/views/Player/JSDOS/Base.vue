<script setup lang="ts">
import { useLocalStorage } from "@vueuse/core";
import { nextTick, onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute } from "vue-router";
import RomListItem from "@/components/common/Game/ListItem.vue";
import type { StateSchema } from "@/__generated__";
import { ROUTES } from "@/plugins/router";
import romApi from "@/services/api/rom";
import { stateApi } from "@/services/api/state";
import storeRoms, { type DetailedRom } from "@/stores/roms";
import type { DosProps, JsDosCI } from "@/types/jsdos";
import { getDownloadPath } from "@/utils";
import { saveJsDosState } from "./utils";

const { t } = useI18n();
const route = useRoute();
const romsStore = storeRoms();
const rom = ref<DetailedRom | null>(null);
const gameRunning = ref(false);
const fullScreenOnPlay = useLocalStorage("emulation.fullScreenOnPlay", true);
const scriptLoaded = ref(false);
const dosCI = ref<JsDosCI | null>(null);
const dosProps = ref<DosProps | null>(null);
const selectedState = ref<StateSchema | null>(null);
const saving = ref(false);

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

    // Download persist data from server if a state is selected
    let initFsData: Uint8Array | undefined;
    if (selectedState.value) {
      try {
        const { data } = await stateApi.get(
          selectedState.value.download_path.replace("/api", ""),
          { responseType: "arraybuffer" },
        );
        if (data) {
          initFsData = new Uint8Array(data);
        }
      } catch (e) {
        console.error("Failed to download js-dos state:", e);
      }
    }

    const props = window.Dos(container as HTMLDivElement, {
      url: getDownloadPath({ rom: rom.value }),
      autoStart: true,
      ...(dosboxConf ? { dosboxConf } : {}),
      ...(initFsData ? { initFs: initFsData } : {}),
      onEvent: (event: string, ci: JsDosCI) => {
        if (event === "ci-ready") {
          dosCI.value = ci;
        }
      },
      onExit: () => {
        gameRunning.value = false;
        dosCI.value = null;
        dosProps.value = null;
      },
    });
    dosProps.value = props;

    if (fullScreenOnPlay.value && document.fullscreenEnabled) {
      container.requestFullscreen?.();
    }
  });
}

function onFullScreenChange() {
  fullScreenOnPlay.value = !fullScreenOnPlay.value;
}

async function saveAndQuit() {
  if (!dosCI.value || !rom.value) return;
  saving.value = true;
  try {
    const persistData = await dosCI.value.persist();
    if (persistData && persistData.length > 0) {
      await saveJsDosState({ rom: rom.value, stateFile: persistData });
      romsStore.update(rom.value);
    }
  } catch (e) {
    console.error("Failed to save js-dos state:", e);
  }
  saving.value = false;
  await dosCI.value.exit();
  dosCI.value = null;
  window.history.back();
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

    // Auto-select the latest js-dos state
    const jsDosStates = rom.value.user_states.filter(
      (s) => s.emulator === "js-dos",
    );
    if (jsDosStates.length > 0) {
      selectedState.value = jsDosStates[0];
    }
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

          <!-- State info when not running -->
          <div v-if="!gameRunning && selectedState" class="mt-4">
            <v-card variant="tonal" color="primary" rounded="lg">
              <v-card-text class="pa-3 text-left">
                <div class="text-caption text-medium-emphasis">
                  {{ t("common.states") }}
                </div>
                <div class="text-body-2 text-truncate">
                  {{ selectedState.file_name }}
                </div>
                <div class="text-caption text-medium-emphasis mt-1">
                  {{ selectedState.updated_at?.substring(0, 19).replace("T", " ") }}
                </div>
              </v-card-text>
            </v-card>
          </div>

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

          <!-- Save & Quit and Quit buttons when running -->
          <div v-if="gameRunning" class="mt-4">
            <v-btn
              block
              color="primary"
              variant="flat"
              size="large"
              prepend-icon="mdi-content-save"
              :loading="saving"
              @click="saveAndQuit"
            >
              {{ t("play.save-and-quit") }}
            </v-btn>
            <v-btn
              class="mt-2"
              block
              variant="outlined"
              size="large"
              prepend-icon="mdi-exit-to-app"
              @click="onlyQuit"
            >
              {{ t("play.quit") }}
            </v-btn>
          </div>
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
