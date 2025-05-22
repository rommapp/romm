<script setup lang="ts">
import EmptySaves from "@/components/common/EmptyStates/EmptySaves.vue";
import EmptyStates from "@/components/common/EmptyStates/EmptyStates.vue";
import type { FirmwareSchema, SaveSchema, StateSchema } from "@/__generated__";
import { formatDistanceToNow } from "date-fns";
import RomListItem from "@/components/common/Game/ListItem.vue";
import firmwareApi from "@/services/api/firmware";
import romApi from "@/services/api/rom";
import storeAuth from "@/stores/auth";
import storePlaying from "@/stores/playing";
import storeRoms, { type DetailedRom } from "@/stores/roms";
import { formatTimestamp, getSupportedEJSCores } from "@/utils";
import { ROUTES } from "@/plugins/router";
import Player from "@/views/Player/EmulatorJS/Player.vue";
import { isNull } from "lodash";
import { onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRoute } from "vue-router";
import { useI18n } from "vue-i18n";
import { saveSave, saveState } from "./utils";
import CacheDialog from "@/views/Player/EmulatorJS/CacheDialog.vue";
import { getEmptyCoverImage } from "@/utils/covers";
import { useDisplay } from "vuetify";
import { storeToRefs } from "pinia";

const EMULATORJS_VERSION = "4.2.1";

// Props
const { t } = useI18n();
const { smAndDown } = useDisplay();
const route = useRoute();
const auth = storeAuth();
const playingStore = storePlaying();
const { playing, fullScreen } = storeToRefs(playingStore);
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
  fullScreen.value = fullScreenOnPlay.value;
  playing.value = true;

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
      playing.value = true;
      fullScreen.value = fullScreenOnPlay.value;
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
  playing.value = false;
  fullScreen.value = false;
  if (rom.value) romsStore.update(rom.value);
  window.history.back();
}

async function saveAndQuit() {
  playing.value = false;
  fullScreen.value = false;
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
  playing.value = false;
  fullScreen.value = false;
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

function formatRelativeDate(date: string | Date) {
  return formatDistanceToNow(new Date(date), { addSuffix: true });
}

watch(selectedCore, (newSelectedCore) => {
  if (
    selectedState.value &&
    selectedState.value.emulator &&
    selectedState.value.emulator !== newSelectedCore
  ) {
    selectedState.value = null;
    localStorage.removeItem(`player:${rom.value?.platform_slug}:state_id`);
  }
});

onMounted(async () => {
  const romResponse = await romApi.getRom({
    romId: parseInt(route.params.rom as string),
  });
  rom.value = romResponse.data;

  if (rom.value) {
    document.title = `${rom.value.name} | Play`;
  }

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
  <!-- TODO: hide main app bar on play if fullscreen -->
  <v-row v-if="rom" class="justify-center scroll px-2" no-gutters>
    <v-col
      v-if="gameRunning"
      cols="12"
      md="8"
      xl="10"
      id="game-wrapper"
      class="bg-background pr-2"
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
      <v-row class="mt-6" no-gutters>
        <v-col>
          <v-img
            class="mx-auto"
            width="250"
            src="/assets/emulatorjs/powered_by_emulatorjs.png"
          />
          <v-divider class="my-4" />
          <rom-list-item :rom="rom" with-filename with-size />
        </v-col>
      </v-row>

      <v-row v-if="!gameRunning" no-gutters>
        <v-col>
          <!-- disc selector -->
          <v-select
            v-if="rom.multi"
            class="mt-4"
            v-model="selectedDisc"
            hide-details
            variant="outlined"
            density="compact"
            prepend-inner-icon="mdi-disc"
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
            class="mt-4"
            v-model="selectedCore"
            hide-details
            variant="outlined"
            prepend-inner-icon="mdi-chip"
            density="compact"
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
            class="mt-4"
            v-model="selectedFirmware"
            hide-details
            variant="outlined"
            density="compact"
            prepend-inner-icon="mdi-memory"
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
            <v-expand-transition>
              <v-col
                v-show="!openSaveSelector || !smAndDown"
                :class="{
                  'mt-2': gameRunning || smAndDown,
                  'pr-1': !smAndDown,
                }"
                :cols="smAndDown ? 12 : 6"
              >
                <v-btn
                  block
                  variant="flat"
                  class="asset-selector"
                  prepend-icon="mdi-file"
                  :color="openStateSelector ? 'primary' : ''"
                  @click="switchStateSelector"
                  :disabled="
                    !rom.user_states.some(
                      (s) => !s.emulator || s.emulator === selectedCore,
                    )
                  "
                >
                  {{
                    selectedState
                      ? t("play.change-state")
                      : t("play.select-state")
                  }}
                </v-btn>
                <v-expand-transition>
                  <v-card
                    v-if="selectedState"
                    class="bg-toplayer transform-scale selected-card mx-1"
                    :class="{ 'disabled-card': openSaveSelector }"
                  >
                    <v-card-text class="px-2 pb-2 pt-4">
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
                        <v-col class="pl-2 d-flex flex-column" cols="6">
                          <v-row
                            class="px-1 text-caption text-primary"
                            no-gutters
                            >{{ selectedState.file_name }}</v-row
                          >
                          <v-row no-gutters>
                            <v-col cols="12">
                              <v-list-item rounded class="px-1 text-caption">
                                Updated:
                                {{ formatTimestamp(selectedState.updated_at) }}
                                <span class="text-grey text-caption"
                                  >({{
                                    formatRelativeDate(
                                      selectedState.updated_at,
                                    )
                                  }})</span
                                >
                              </v-list-item>
                            </v-col>
                            <v-col v-if="selectedState.emulator" cols="12">
                              <v-chip size="x-small" color="orange" label>
                                {{ selectedState.emulator }}
                              </v-chip>
                            </v-col>
                          </v-row>
                          <v-row no-gutters>
                            <v-col class="text-right mt-auto pt-1">
                              <v-btn
                                variant="flat"
                                color="toplayer"
                                size="small"
                                icon
                                @click="unselectState()"
                              >
                                <v-icon>mdi-close-circle-outline</v-icon>
                              </v-btn>
                            </v-col>
                          </v-row>
                        </v-col>
                      </v-row>
                    </v-card-text>
                  </v-card>
                </v-expand-transition>
              </v-col>
            </v-expand-transition>

            <!-- save selector -->
            <v-expand-transition>
              <v-col
                v-show="!openStateSelector || !smAndDown"
                :class="{
                  'mt-2': gameRunning || smAndDown,
                  'pl-1': !smAndDown,
                }"
                :cols="smAndDown ? 12 : 6"
              >
                <v-btn
                  block
                  variant="flat"
                  class="asset-selector"
                  prepend-icon="mdi-content-save"
                  :color="openSaveSelector ? 'primary' : ''"
                  @click="switchSaveSelector"
                >
                  {{
                    selectedSave ? t("play.change-save") : t("play.select-save")
                  }}
                </v-btn>
                <v-expand-transition>
                  <v-card
                    v-if="selectedSave"
                    class="bg-toplayer transform-scale selected-card mx-1"
                    :class="{ 'disabled-card': openStateSelector }"
                  >
                    <v-card-text class="px-2 pb-2 pt-4">
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
                        <v-col class="pl-2 d-flex flex-column" cols="6">
                          <v-row
                            class="px-1 text-caption text-primary"
                            no-gutters
                            >{{ selectedSave.file_name }}</v-row
                          >
                          <v-row no-gutters>
                            <v-col cols="12">
                              <v-list-item rounded class="px-1 text-caption">
                                Updated:
                                {{ formatTimestamp(selectedSave.updated_at) }}
                                <span class="text-grey text-caption"
                                  >({{
                                    formatRelativeDate(selectedSave.updated_at)
                                  }})</span
                                >
                              </v-list-item>
                            </v-col>
                            <v-col v-if="selectedSave.emulator" cols="12">
                              <v-chip size="x-small" color="orange" label>
                                {{ selectedSave.emulator }}
                              </v-chip>
                            </v-col>
                          </v-row>
                          <v-row no-gutters>
                            <v-col class="text-right mt-auto pt-2">
                              <v-btn
                                variant="flat"
                                color="toplayer"
                                size="small"
                                icon
                                @click="unselectSave()"
                              >
                                <v-icon>mdi-close-circle-outline</v-icon>
                              </v-btn>
                            </v-col>
                          </v-row>
                        </v-col>
                      </v-row>
                    </v-card-text>
                  </v-card>
                </v-expand-transition>
              </v-col>
            </v-expand-transition>
          </v-row>

          <!-- state display -->
          <v-expand-transition>
            <v-row v-if="openStateSelector" class="mt-2" no-gutters>
              <v-col
                cols="6"
                sm="4"
                class="pa-1"
                v-if="rom.user_states.length > 0"
                v-for="state in rom.user_states
                  .filter((s) => !s.emulator || s.emulator === selectedCore)
                  .sort((a, b) => {
                    return (
                      new Date(b.updated_at).getTime() -
                      new Date(a.updated_at).getTime()
                    );
                  })"
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
                      <v-row
                        class="py-2 px-1 text-caption text-primary"
                        no-gutters
                        >{{ state.file_name }}</v-row
                      >
                      <v-row class="ga-1" no-gutters>
                        <v-col cols="12">
                          <v-list-item rounded class="pa-1 text-caption">
                            Updated: {{ formatTimestamp(state.updated_at) }}
                            <span class="ml-1 text-grey text-caption"
                              >({{
                                formatRelativeDate(state.updated_at)
                              }})</span
                            >
                          </v-list-item>
                        </v-col>
                        <v-col v-if="state.emulator" cols="12" class="mt-1">
                          <v-chip size="x-small" color="orange" label>
                            {{ state.emulator }}
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
                v-for="save in rom.user_saves.sort((a, b) => {
                  return (
                    new Date(b.updated_at).getTime() -
                    new Date(a.updated_at).getTime()
                  );
                })"
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
                      <v-row
                        class="py-2 px-1 text-caption text-primary"
                        no-gutters
                        >{{ save.file_name }}</v-row
                      >
                      <v-row class="ga-1" no-gutters>
                        <v-col cols="12">
                          <v-list-item rounded class="pa-1 text-caption">
                            Updated: {{ formatTimestamp(save.updated_at) }}
                            <span class="ml-1 text-grey text-caption"
                              >({{ formatRelativeDate(save.updated_at) }})</span
                            >
                          </v-list-item>
                        </v-col>
                        <v-col v-if="save.emulator" cols="12" class="mt-1">
                          <v-chip size="x-small" color="orange" label>
                            {{ save.emulator }}
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
      <template v-if="!gameRunning">
        <v-row class="align-center mt-4" no-gutters>
          <v-col :class="{ 'pr-1': !smAndDown }">
            <v-btn
              block
              @click="onFullScreenChange"
              variant="flat"
              :append-icon="
                fullScreenOnPlay ? 'mdi-fullscreen' : 'mdi-fullscreen-exit'
              "
              :color="fullScreenOnPlay ? 'primary' : ''"
              ><v-icon class="mr-2">{{
                fullScreenOnPlay
                  ? "mdi-checkbox-outline"
                  : "mdi-checkbox-blank-outline"
              }}</v-icon
              >{{ t("play.full-screen") }}</v-btn
            >
          </v-col>
          <v-col
            :cols="smAndDown ? 12 : 8"
            :class="smAndDown ? 'mt-2' : 'pl-1'"
          >
            <v-btn
              block
              variant="flat"
              class="text-primary"
              prepend-icon="mdi-play"
              @click="onPlay()"
              >{{ t("play.play") }}
            </v-btn>
          </v-col>
        </v-row>
        <v-row class="align-center my-4" no-gutters>
          <v-col
            :class="{ 'mt-2': gameRunning || smAndDown, 'pr-1': !smAndDown }"
            :cols="smAndDown ? 12 : 6"
          >
            <v-btn
              block
              variant="flat"
              prepend-icon="mdi-arrow-left"
              append-icon="mdi-details"
              @click="
                $router.push({
                  name: ROUTES.ROM,
                  params: { rom: rom?.id },
                })
              "
              >{{ t("play.back-to-game-details") }}
            </v-btn>
          </v-col>
          <v-col
            :class="{ 'mt-2': gameRunning || smAndDown, 'pl-1': !smAndDown }"
            :cols="smAndDown ? 12 : 6"
          >
            <v-btn
              block
              variant="flat"
              prepend-icon="mdi-arrow-left"
              append-icon="mdi-apps"
              @click="
                $router.push({
                  name: ROUTES.PLATFORM,
                  params: { platform: rom?.platform_id },
                })
              "
              >{{ t("play.back-to-gallery") }}
            </v-btn>
          </v-col>
        </v-row>
      </template>
      <v-row v-else class="align-center my-4" no-gutters>
        <v-btn
          :class="{ 'mt-2': gameRunning || smAndDown, 'pr-1': !smAndDown }"
          block
          variant="flat"
          prepend-icon="mdi-exit-to-app"
          @click="onlyQuit"
        >
          {{ t("play.quit") }}
        </v-btn>
        <v-btn
          :class="{ 'mt-2': gameRunning || smAndDown, 'pl-1': !smAndDown }"
          block
          variant="flat"
          prepend-icon="mdi-content-save-move"
          @click="saveAndQuit"
        >
          {{ t("play.save-and-quit") }}
        </v-btn>
      </v-row>
      <cache-dialog v-if="!gameRunning" />
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

.selected-card {
  margin-top: -5px;
}

.disabled-card {
  opacity: 0.2;
}

.asset-selector {
  z-index: 11;
}
</style>
