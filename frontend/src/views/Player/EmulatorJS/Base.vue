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
import { onBeforeUnmount, onMounted, ref } from "vue";
import { useRoute } from "vue-router";
import { useI18n } from "vue-i18n";
import { saveSave, saveState } from "./utils";
import CacheDialog from "@/views/Player/EmulatorJS/CacheDialog.vue";
import { getEmptyCoverImage } from "@/utils/covers";
import { useDisplay } from "vuetify";

const EMULATORJS_VERSION = "4.2.1";

// Props
const { t } = useI18n();
const { smAndDown } = useDisplay();
const route = useRoute();
const auth = storeAuth();
const romsStore = storeRoms();
const rom = ref<DetailedRom | null>(null);
const firmwareOptions = ref<FirmwareSchema[]>([]);
const selectedFirmware = ref<FirmwareSchema | null>(null);
const selectedSave = ref<SaveSchema | null>(null);
const openSaveSelector = ref(false);
const selectedState = ref<StateSchema | null>(null);
const openStateSelector = ref(false);
const selectedCore = ref<string | null>(null);
const selectedDisc = ref<number | null>(null);
const supportedCores = ref<string[]>([]);
const gameRunning = ref(false);
const storedFSOP = localStorage.getItem("fullScreenOnPlay");
const fullScreenOnPlay = ref(isNull(storedFSOP) ? true : storedFSOP === "true");

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

function switchSaveSelector() {
  openSaveSelector.value = !openSaveSelector.value;
  openStateSelector.value = false;
}

function selectSave(save: SaveSchema) {
  selectedSave.value = save;
  localStorage.setItem(
    `player:${rom.value?.platform_slug}:save_id`,
    save.id.toString(),
  );
  openSaveSelector.value = false;
}

function unselectSave() {
  selectedSave.value = null;
  localStorage.removeItem(`player:${rom.value?.platform_slug}:save_id`);
}

function switchStateSelector() {
  openStateSelector.value = !openStateSelector.value;
  openSaveSelector.value = false;
}

function selectState(state: StateSchema) {
  selectedState.value = state;
  localStorage.setItem(
    `player:${rom.value?.platform_slug}:state_id`,
    state.id.toString(),
  );
  openStateSelector.value = false;
}

function unselectState() {
  selectedState.value = null;
  localStorage.removeItem(`player:${rom.value?.platform_slug}:state_id`);
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
});

onBeforeUnmount(async () => {
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
      <!-- Header -->
      <v-row class="px-3 mt-6" no-gutters>
        <v-col>
          <v-img
            class="mx-auto"
            width="250"
            src="/assets/emulatorjs/powered_by_emulatorjs.png"
          />
          <v-divider class="mb-4 mt-8" />
          <rom-list-item :rom="rom" with-filename with-size />
        </v-col>
      </v-row>

      <v-row v-if="!gameRunning" class="px-3 py-3" no-gutters>
        <v-col>
          <!-- disc selector -->
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
          <!-- core selector -->
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
          <!-- bios selector -->
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

          <!-- save/satate selector -->
          <v-row class="mt-4" no-gutters>
            <!-- state selector -->
            <v-col
              :class="gameRunning || smAndDown ? 'mt-2' : 'pr-1'"
              :cols="smAndDown ? 12 : 6"
            >
              <v-row no-gutters>
                <v-col>
                  <v-btn
                    block
                    variant="outlined"
                    size="large"
                    prepend-icon="mdi-file"
                    :color="openStateSelector ? 'primary' : ''"
                    @click="switchStateSelector"
                  >
                    {{
                      selectedState
                        ? t("play.change-state")
                        : t("play.select-state")
                    }}
                  </v-btn>
                </v-col>
              </v-row>
              <v-expand-transition>
                <v-card
                  v-if="selectedState"
                  class="bg-toplayer transform-scale"
                  :class="{ 'disabled-card': openSaveSelector }"
                >
                  <v-card-text class="px-2 pb-2">
                    <v-row no-gutters>
                      <v-col cols="6">
                        <v-img
                          rounded
                          :src="
                            selectedState.screenshot?.download_path ??
                            getEmptyCoverImage(selectedState.file_name)
                          "
                        >
                        </v-img>
                      </v-col>
                      <v-col class="pl-2" cols="6">
                        <v-row class="text-caption" no-gutters>{{
                          selectedState.file_name
                        }}</v-row>
                        <v-row class="ga-1" no-gutters>
                          <v-col v-if="selectedState.emulator" cols="12">
                            <v-chip size="x-small" color="orange" label>
                              {{ selectedState.emulator }}
                            </v-chip>
                          </v-col>
                          <v-col cols="12">
                            <v-chip size="x-small" label>
                              {{ formatBytes(selectedState.file_size_bytes) }}
                            </v-chip>
                          </v-col>
                          <v-col cols="12">
                            <v-chip size="x-small" label>
                              Updated:
                              {{ formatTimestamp(selectedState.updated_at) }}
                            </v-chip>
                          </v-col>
                        </v-row>
                      </v-col>
                    </v-row>
                    <v-row class="mt-2" no-gutters>
                      <v-col>
                        <v-btn
                          block
                          variant="outlined"
                          @click="unselectState()"
                        >
                          <v-icon class="mr-2">mdi-close-circle-outline</v-icon
                          >{{ t("play.deselect-state") }}
                        </v-btn>
                      </v-col>
                    </v-row>
                  </v-card-text>
                </v-card>
              </v-expand-transition>
            </v-col>

            <!-- save selector -->
            <v-col
              :class="gameRunning || smAndDown ? 'mt-2' : 'pl-1'"
              :cols="smAndDown ? 12 : 6"
            >
              <v-row no-gutters>
                <v-col>
                  <v-btn
                    block
                    variant="outlined"
                    prepend-icon="mdi-content-save"
                    size="large"
                    :color="openSaveSelector ? 'primary' : ''"
                    @click="switchSaveSelector"
                  >
                    {{
                      selectedSave
                        ? t("play.change-save")
                        : t("play.select-save")
                    }}
                  </v-btn>
                </v-col>
              </v-row>
              <v-expand-transition>
                <v-card
                  v-if="selectedSave"
                  class="bg-toplayer transform-scale"
                  :class="{ 'disabled-card': openStateSelector }"
                >
                  <v-card-text class="px-2 pb-2">
                    <v-row no-gutters>
                      <v-col cols="6">
                        <v-img
                          rounded
                          :src="
                            selectedSave.screenshot?.download_path ??
                            getEmptyCoverImage(selectedSave.file_name)
                          "
                        >
                        </v-img>
                      </v-col>
                      <v-col class="pl-2" cols="6">
                        <v-row class="text-caption" no-gutters>{{
                          selectedSave.file_name
                        }}</v-row>
                        <v-row class="ga-1" no-gutters>
                          <v-col v-if="selectedSave.emulator" cols="12">
                            <v-chip size="x-small" color="orange" label>
                              {{ selectedSave.emulator }}
                            </v-chip>
                          </v-col>
                          <v-col cols="12">
                            <v-chip size="x-small" label>
                              {{ formatBytes(selectedSave.file_size_bytes) }}
                            </v-chip>
                          </v-col>
                          <v-col cols="12">
                            <v-chip size="x-small" label>
                              Updated:
                              {{ formatTimestamp(selectedSave.updated_at) }}
                            </v-chip>
                          </v-col>
                        </v-row>
                      </v-col>
                    </v-row>
                    <v-row class="mt-2" no-gutters>
                      <v-col>
                        <v-btn block variant="outlined" @click="unselectSave()">
                          <v-icon class="mr-2">mdi-close-circle-outline</v-icon
                          >{{ t("play.deselect-save") }}
                        </v-btn>
                      </v-col>
                    </v-row>
                  </v-card-text>
                </v-card>
              </v-expand-transition>
            </v-col>
          </v-row>

          <!-- state display -->
          <v-expand-transition>
            <v-row v-if="openStateSelector" class="mt-2" no-gutters>
              <v-col
                cols="6"
                sm="4"
                class="pa-1"
                v-if="rom.user_states.length > 0"
                v-for="state in rom.user_states"
              >
                <v-hover v-slot="{ isHovering, props }">
                  <v-card
                    :style="{
                      zIndex: selectedState?.id === state.id ? 11 : undefined,
                    }"
                    v-bind="props"
                    class="bg-toplayer transform-scale"
                    :class="{
                      'on-hover': isHovering,
                      'border-selected': selectedState?.id === state.id,
                    }"
                    :elevation="isHovering ? 20 : 3"
                    @click="selectState(state)"
                  >
                    <v-card-text class="pa-2">
                      <v-row no-gutters>
                        <v-col cols="12">
                          <v-img
                            rounded
                            :src="
                              state.screenshot?.download_path ??
                              getEmptyCoverImage(state.file_name)
                            "
                          >
                          </v-img>
                        </v-col>
                      </v-row>
                      <v-row class="py-2 text-caption" no-gutters>{{
                        state.file_name
                      }}</v-row>
                      <v-row class="ga-1" no-gutters>
                        <v-col v-if="state.emulator" cols="12">
                          <v-chip size="x-small" color="orange" label>
                            {{ state.emulator }}
                          </v-chip>
                        </v-col>
                        <v-col cols="12">
                          <v-chip size="x-small" label>
                            {{ formatBytes(state.file_size_bytes) }}
                          </v-chip>
                        </v-col>
                        <v-col cols="12">
                          <v-chip size="x-small" label>
                            Updated: {{ formatTimestamp(state.updated_at) }}
                          </v-chip>
                        </v-col>
                      </v-row>
                    </v-card-text>
                  </v-card>
                </v-hover>
              </v-col>
              <v-col v-else class="pa-1 mt-1">
                <empty-states />
              </v-col>
            </v-row>
          </v-expand-transition>

          <!-- save display -->
          <v-expand-transition>
            <v-row v-if="openSaveSelector" class="mt-2" no-gutters>
              <v-col
                cols="6"
                sm="4"
                class="pa-1"
                v-if="rom.user_saves.length > 0"
                v-for="save in rom.user_saves"
              >
                <v-hover v-slot="{ isHovering, props }">
                  <v-card
                    :style="{
                      zIndex: selectedSave?.id === save.id ? 11 : undefined,
                    }"
                    v-bind="props"
                    class="bg-toplayer transform-scale"
                    :class="{
                      'on-hover': isHovering,
                      'border-selected': selectedSave?.id === save.id,
                    }"
                    :elevation="isHovering ? 20 : 3"
                    @click="selectSave(save)"
                  >
                    <v-card-text class="pa-2">
                      <v-row no-gutters>
                        <v-col cols="12">
                          <v-img
                            rounded
                            :src="
                              save.screenshot?.download_path ??
                              getEmptyCoverImage(save.file_name)
                            "
                          >
                          </v-img>
                        </v-col>
                      </v-row>
                      <v-row class="py-2 text-caption" no-gutters>{{
                        save.file_name
                      }}</v-row>
                      <v-row class="ga-1" no-gutters>
                        <v-col v-if="save.emulator" cols="12">
                          <v-chip size="x-small" color="orange" label>
                            {{ save.emulator }}
                          </v-chip>
                        </v-col>
                        <v-col cols="12">
                          <v-chip size="x-small" label>
                            {{ formatBytes(save.file_size_bytes) }}
                          </v-chip>
                        </v-col>
                        <v-col cols="12">
                          <v-chip size="x-small" label>
                            Updated: {{ formatTimestamp(save.updated_at) }}
                          </v-chip>
                        </v-col>
                      </v-row>
                    </v-card-text>
                  </v-card>
                </v-hover>
              </v-col>
              <v-col v-else class="pa-1 mt-1">
                <empty-saves />
              </v-col>
            </v-row>
          </v-expand-transition>
        </v-col>
      </v-row>

      <!-- Action buttons -->
      <v-row class="px-3 py-2 text-center" no-gutters>
        <v-col>
          <v-row v-if="!gameRunning" class="align-center" no-gutters>
            <v-col :class="smAndDown ? '' : 'pr-1'">
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
              :class="gameRunning || smAndDown ? 'mt-2' : 'pl-1'"
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

.disabled-card {
  opacity: 0.2;
}
</style>
