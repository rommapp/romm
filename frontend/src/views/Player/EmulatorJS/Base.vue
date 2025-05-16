<script setup lang="ts">
import EmptySaves from "@/components/common/EmptyStates/EmptySaves.vue";
import EmptyStates from "@/components/common/EmptyStates/EmptyStates.vue";
import type { FirmwareSchema, SaveSchema, StateSchema } from "@/__generated__";
import RomListItem from "@/components/common/Game/ListItem.vue";
import firmwareApi from "@/services/api/firmware";
import romApi from "@/services/api/rom";
import storeAuth from "@/stores/auth";
import storeRoms, { type DetailedRom } from "@/stores/roms";
import { formatBytes, formatTimestamp, getSupportedEJSCores } from "@/utils";
import { ROUTES } from "@/plugins/router";
import Player from "@/views/Player/EmulatorJS/Player.vue";
import { isNull } from "lodash";
import { inject, onBeforeUnmount, onMounted, ref } from "vue";
import { useRoute } from "vue-router";
import { useI18n } from "vue-i18n";
import { saveSave, saveState } from "./utils";
import CacheDialog from "@/views/Player/EmulatorJS/CacheDialog.vue";
import type { Emitter } from "mitt";
import type { Events } from "@/types/emitter";
import { getEmptyCoverImage } from "@/utils/covers";
import { useDisplay } from "vuetify";

const EMULATORJS_VERSION = "4.2.1";

// Props
const { t } = useI18n();
const { smAndDown } = useDisplay();
const route = useRoute();
const auth = storeAuth();
const romsStore = storeRoms();
const tab = ref<"saves" | "states">("saves");
const rom = ref<DetailedRom | null>(null);
const firmwareOptions = ref<FirmwareSchema[]>([]);
const selectedFirmware = ref<FirmwareSchema | null>(null);
const selectedSave = ref<SaveSchema | null>(null);
const selectedState = ref<StateSchema | null>(null);
const selectedCore = ref<string | null>(null);
const selectedDisc = ref<number | null>(null);
const supportedCores = ref<string[]>([]);
const gameRunning = ref(false);
const storedFSOP = localStorage.getItem("fullScreenOnPlay");
const fullScreenOnPlay = ref(isNull(storedFSOP) ? true : storedFSOP === "true");
const emitter = inject<Emitter<Events>>("emitter");

// Functions
function onPlay() {
  if (rom.value && auth.scopes.includes("roms.user.write")) {
    romApi.updateUserRomProps({
      romId: rom.value.id,
      data: rom.value.rom_user,
      updateLastPlayed: true,
    });
  }

  gameRunning.value = true;
  window.EJS_fullscreenOnLoaded = fullScreenOnPlay.value;

  const LOCAL_PATH = "/assets/emulatorjs/data/";
  const CDN_PATH = `https://cdn.emulatorjs.org/${EMULATORJS_VERSION}/data/`;

  // Try loading local loader.js via fetch to validate it's real JS
  fetch(`${LOCAL_PATH}loader.js`)
    .then((res) => {
      const type = res.headers.get("content-type") || "";
      if (!res.ok || !type.includes("javascript")) {
        throw new Error("Invalid local loader.js");
      }
      window.EJS_pathtodata = LOCAL_PATH;
      return res.text();
    })
    .then((jsCode) => {
      const script = document.createElement("script");
      script.textContent = jsCode;
      document.body.appendChild(script);
    })
    .catch(() => {
      console.warn("Local EmulatorJS failed, falling back to CDN");
      window.EJS_pathtodata = CDN_PATH;
      const fallbackScript = document.createElement("script");
      fallbackScript.src = `${CDN_PATH}loader.js`;
      document.body.appendChild(fallbackScript);
    });
}

function onFullScreenChange() {
  fullScreenOnPlay.value = !fullScreenOnPlay.value;
  localStorage.setItem("fullScreenOnPlay", fullScreenOnPlay.value.toString());
}

async function onlyQuit() {
  if (rom.value) romsStore.update(rom.value);
  window.history.back();
}

async function saveAndQuit() {
  if (!rom.value) return window.history.back();
  const screenshotFile = await window.EJS_emulator.gameManager.screenshot();

  // Force a save of the current state
  const stateFile = window.EJS_emulator.gameManager.getState();
  await saveState({
    rom: rom.value,
    stateFile,
    screenshotFile,
  });

  // Force a save of the save file
  const saveFile = window.EJS_emulator.gameManager.getSaveFile();
  await saveSave({
    rom: rom.value,
    save: selectedSave.value,
    saveFile,
    screenshotFile,
  });

  romsStore.update(rom.value);
  window.history.back();
}

function selectSave(save: SaveSchema) {
  selectedSave.value = save;
  localStorage.setItem(
    `player:${rom.value?.platform_slug}:save_id`,
    save.id.toString(),
  );
}

function selectState(state: StateSchema) {
  selectedState.value = state;
  localStorage.setItem(
    `player:${rom.value?.platform_slug}:state_id`,
    state.id.toString(),
  );
}

onMounted(async () => {
  const romResponse = await romApi.getRom({
    romId: parseInt(route.params.rom as string),
  });
  rom.value = romResponse.data;

  const firmwareResponse = await firmwareApi.getFirmware({
    platformId: romResponse.data.platform_id,
  });
  firmwareOptions.value = firmwareResponse.data;

  supportedCores.value = [...getSupportedEJSCores(rom.value.platform_slug)];

  // Load stored bios, save, state, and core
  selectedSave.value = rom.value.user_saves[0] ?? null;
  selectedState.value = rom.value.user_states[0] ?? null;

  const storedBiosID = localStorage.getItem(
    `player:${rom.value.platform_slug}:bios_id`,
  );
  if (storedBiosID) {
    selectedFirmware.value =
      firmwareOptions.value.find((f) => f.id === parseInt(storedBiosID)) ??
      null;
  }

  const storedCore = localStorage.getItem(
    `player:${rom.value.platform_slug}:core`,
  );
  if (storedCore) {
    selectedCore.value = storedCore;
  } else {
    // Otherwise auto select first supported core
    selectedCore.value = supportedCores.value[0];
  }

  const storedDisc = localStorage.getItem(`player:${rom.value.id}:disc`);
  if (storedDisc) {
    selectedDisc.value = parseInt(storedDisc);
  }

  emitter?.on("saveSelected", selectSave);
  emitter?.on("stateSelected", selectState);
});

onBeforeUnmount(async () => {
  emitter?.off("saveSelected", selectSave);
  emitter?.off("stateSelected", selectState);
  window.EJS_emulator?.callEvent("exit");
});
</script>

<template>
  <v-row v-if="rom" class="justify-center scroll" no-gutters>
    <v-col
      v-if="gameRunning"
      cols="12"
      md="8"
      xl="10"
      id="game-wrapper"
      class="bg-background"
      rounded
    >
      <player
        :rom="rom"
        :state="selectedState"
        :save="selectedSave"
        :bios="selectedFirmware"
        :core="selectedCore"
        :disc="selectedDisc"
      />
    </v-col>

    <v-col
      cols="12"
      sm="10"
      :md="!gameRunning ? 8 : 4"
      :xl="!gameRunning ? 6 : 2"
    >
      <v-row class="px-3 mt-6" no-gutters>
        <v-col>
          <v-img
            class="mx-auto"
            width="250"
            src="/assets/emulatorjs/powered_by_emulatorjs.png"
          />
          <v-divider class="my-4 mt-8" />
          <rom-list-item :rom="rom" with-filename with-size />
        </v-col>
      </v-row>
      <v-row v-if="!gameRunning" class="px-3 py-3" no-gutters>
        <v-col>
          <v-select
            v-if="rom.multi"
            v-model="selectedDisc"
            class="my-1"
            hide-details
            rounded="0"
            variant="outlined"
            clearable
            :label="t('rom.file')"
            :items="
              rom.files.map((f) => ({
                title: f.file_name,
                value: f.id,
              }))
            "
          />
          <v-select
            v-if="supportedCores.length > 1"
            v-model="selectedCore"
            class="my-1"
            hide-details
            variant="outlined"
            clearable
            :label="t('common.core')"
            :items="
              supportedCores.map((c) => ({
                title: c,
                value: c,
              }))
            "
          />
          <v-select
            v-if="firmwareOptions.length > 0"
            v-model="selectedFirmware"
            class="my-1"
            hide-details
            variant="outlined"
            clearable
            :label="t('common.firmware')"
            :items="
              firmwareOptions.map((f) => ({
                title: f.file_name,
                value: f,
              })) ?? []
            "
          />
          <v-row class="mt-2">
            <v-col :cols="smAndDown ? 12 : 6">
              <v-card v-if="selectedState" class="bg-toplayer transform-scale">
                <v-card-text class="d-flex flex-row justify-end h-100">
                  <v-col class="pa-0">
                    <v-img
                      cover
                      height="100%"
                      :src="
                        selectedState.screenshot?.download_path ??
                        getEmptyCoverImage(selectedState.file_name)
                      "
                    />
                  </v-col>
                  <v-col class="ml-4">
                    <v-row class="text-h6">{{
                      t("play.select-state").toUpperCase()
                    }}</v-row>
                    <v-row class="mt-4 flex-grow-0">{{
                      selectedState.file_name
                    }}</v-row>
                    <v-row
                      class="mt-6 d-flex flex-md-wrap ga-2 flex-grow-0"
                      style="min-height: 20px"
                    >
                      <v-chip
                        v-if="selectedState.emulator"
                        size="x-small"
                        color="orange"
                        label
                      >
                        {{ selectedState.emulator }}
                      </v-chip>
                      <v-chip size="x-small" label>
                        {{ formatBytes(selectedState.file_size_bytes) }}
                      </v-chip>
                      <v-chip size="x-small" label>
                        {{ formatTimestamp(selectedState.updated_at) }}
                      </v-chip>
                      <v-btn
                        class="w-100 mt-4"
                        variant="outlined"
                        size="large"
                        @click="selectedState = null"
                      >
                        <v-icon>mdi-close-circle-outline</v-icon>
                      </v-btn>
                    </v-row>
                  </v-col>
                </v-card-text>
              </v-card>
              <v-row v-else>
                <v-col>
                  <v-btn
                    class="w-100"
                    variant="outlined"
                    size="large"
                    @click="emitter?.emit('selectStateDialog', rom)"
                  >
                    {{ t("play.select-state") }}
                  </v-btn>
                </v-col>
              </v-row>
            </v-col>
            <v-col :cols="smAndDown ? 12 : 6">
              <v-card v-if="selectedSave" class="bg-toplayer transform-scale">
                <v-card-text class="d-flex flex-row justify-end h-100">
                  <v-col class="pa-0">
                    <v-img
                      cover
                      height="100%"
                      :src="
                        selectedSave.screenshot?.download_path ??
                        getEmptyCoverImage(selectedSave.file_name)
                      "
                    />
                  </v-col>
                  <v-col class="ml-4">
                    <v-row class="text-h6">{{
                      t("play.select-save").toUpperCase()
                    }}</v-row>
                    <v-row class="mt-4 flex-grow-0">{{
                      selectedSave.file_name
                    }}</v-row>
                    <v-row
                      class="mt-6 d-flex flex-md-wrap ga-2 flex-grow-0"
                      style="min-height: 20px"
                    >
                      <v-chip
                        v-if="selectedSave.emulator"
                        size="x-small"
                        color="orange"
                        label
                      >
                        {{ selectedSave.emulator }}
                      </v-chip>
                      <v-chip size="x-small" label>
                        {{ formatBytes(selectedSave.file_size_bytes) }}
                      </v-chip>
                      <v-chip size="x-small" label>
                        {{ formatTimestamp(selectedSave.updated_at) }}
                      </v-chip>
                      <v-btn
                        class="w-100 mt-4"
                        variant="outlined"
                        size="large"
                        @click="selectedSave = null"
                      >
                        <v-icon>mdi-close-circle-outline</v-icon>
                      </v-btn>
                    </v-row>
                  </v-col>
                </v-card-text>
              </v-card>
              <v-row v-else>
                <v-col>
                  <v-btn
                    class="w-100"
                    variant="outlined"
                    size="large"
                    @click="emitter?.emit('selectSaveDialog', rom)"
                  >
                    {{ t("play.select-save") }}
                  </v-btn>
                </v-col>
              </v-row>
            </v-col>
          </v-row>
        </v-col>
      </v-row>
      <v-row class="px-3 py-3 text-center" no-gutters>
        <v-col>
          <v-row v-if="!gameRunning" class="align-center" no-gutters>
            <v-col>
              <v-btn
                block
                size="large"
                @click="onFullScreenChange"
                :disabled="gameRunning"
                :variant="fullScreenOnPlay ? 'flat' : 'outlined'"
                :color="fullScreenOnPlay ? 'primary' : ''"
                ><v-icon class="mr-1">{{
                  fullScreenOnPlay
                    ? "mdi-checkbox-outline"
                    : "mdi-checkbox-blank-outline"
                }}</v-icon
                >{{ t("play.full-screen") }}</v-btn
              >
            </v-col>
            <v-col
              :cols="gameRunning || smAndDown ? 12 : 8"
              :class="gameRunning || smAndDown ? 'mt-2' : 'ml-4'"
            >
              <v-btn
                color="primary"
                block
                :disabled="gameRunning"
                variant="outlined"
                size="large"
                prepend-icon="mdi-play"
                @click="onPlay()"
                >{{ t("play.play") }}
              </v-btn>
            </v-col>
          </v-row>
          <v-row v-if="!gameRunning" class="align-center" no-gutters>
            <v-btn
              class="mt-4"
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
              >{{ t("play.back-to-game-details") }}
            </v-btn>
            <v-btn
              class="mt-4"
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
              >{{ t("play.back-to-gallery") }}
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
          <v-btn
            v-if="gameRunning"
            class="mt-4"
            block
            variant="outlined"
            size="large"
            prepend-icon="mdi-content-save-move"
            @click="saveAndQuit"
          >
            {{ t("play.save-and-quit") }}
          </v-btn>
          <cache-dialog v-if="!gameRunning" />
        </v-col>
      </v-row>
    </v-col>
  </v-row>
</template>

<style scoped>
#game-wrapper {
  height: 100vh;
}

@media (max-width: 960px) {
  #game-wrapper {
    height: calc(100vh - 55px);
  }
}
</style>
