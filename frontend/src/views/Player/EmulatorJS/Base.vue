<script setup lang="ts">
import { useLocalStorage } from "@vueuse/core";
import { storeToRefs } from "pinia";
import { onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute } from "vue-router";
import { useDisplay } from "vuetify";
import type { FirmwareSchema, SaveSchema, StateSchema } from "@/__generated__";
import EmptySaves from "@/components/common/EmptyStates/EmptySaves.vue";
import EmptyStates from "@/components/common/EmptyStates/EmptyStates.vue";
import AssetCard from "@/components/common/Game/AssetCard.vue";
import RomListItem from "@/components/common/Game/ListItem.vue";
import { ROUTES } from "@/plugins/router";
import firmwareApi from "@/services/api/firmware";
import romApi from "@/services/api/rom";
import storeAuth from "@/stores/auth";
import storeConfig from "@/stores/config";
import storePlaying from "@/stores/playing";
import { type DetailedRom } from "@/stores/roms";
import {
  formatTimestamp,
  getSupportedEJSCores,
  formatRelativeDate,
} from "@/utils";
import { getEmptyCoverImage } from "@/utils/covers";
import CacheDialog from "@/views/Player/EmulatorJS/CacheDialog.vue";
import Player from "@/views/Player/EmulatorJS/Player.vue";

const { t, locale } = useI18n();
const { smAndDown } = useDisplay();
const route = useRoute();
const auth = storeAuth();
const playingStore = storePlaying();
const configStore = storeConfig();
const { playing, fullScreen } = storeToRefs(playingStore);
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
const fullScreenOnPlay = useLocalStorage("emulation.fullScreenOnPlay", true);

async function onPlay() {
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

  const { EJS_NETPLAY_ENABLED } = configStore.config;
  const EMULATORJS_VERSION = EJS_NETPLAY_ENABLED ? "nightly" : "4.2.3";
  const LOCAL_PATH = "/assets/emulatorjs/data";
  const CDN_PATH = `https://cdn.emulatorjs.org/${EMULATORJS_VERSION}/data`;

  function loadScript(src: string): Promise<void> {
    return new Promise((resolve, reject) => {
      const s = document.createElement("script");
      s.src = src;
      s.async = true;
      s.onload = () => resolve();
      s.onerror = () => reject(new Error("Failed loading " + src));
      document.body.appendChild(s);
    });
  }

  async function attemptLoad(path: string) {
    window.EJS_pathtodata = path;
    await loadScript(`${path}/loader.js`);
  }

  try {
    try {
      await attemptLoad(EJS_NETPLAY_ENABLED ? CDN_PATH : LOCAL_PATH);
    } catch (e) {
      console.warn("[Play] Local loader failed, trying CDN", e);
      await attemptLoad(EJS_NETPLAY_ENABLED ? LOCAL_PATH : CDN_PATH);
    }
    playing.value = true;
    fullScreen.value = fullScreenOnPlay.value;
  } catch (err) {
    console.error("[Play] Emulator load failure:", err);
  }
}

function onFullScreenChange() {
  fullScreenOnPlay.value = !fullScreenOnPlay.value;
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
  <v-row v-if="rom" class="align-center justify-center scroll h-100" no-gutters>
    <v-col v-if="!gameRunning" cols="12" sm="10" md="8" xl="6">
      <!-- Header -->
      <v-row no-gutters>
        <v-col>
          <v-img
            class="mx-auto"
            width="150"
            src="/assets/emulatorjs/emulatorjs.svg"
          />
        </v-col>
      </v-row>

      <v-divider class="my-4 mx-2" />

      <v-row no-gutters>
        <v-col>
          <RomListItem :rom="rom" with-filename with-size />
        </v-col>
      </v-row>

      <v-row class="mx-2" no-gutters>
        <v-col>
          <!-- disc selector -->
          <v-select
            v-if="rom.has_multiple_files"
            v-model="selectedDisc"
            class="mt-4"
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
            v-model="selectedCore"
            class="mt-4"
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
            v-model="selectedFirmware"
            class="mt-4"
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
                  'mt-2': smAndDown,
                  'pr-1': !smAndDown,
                }"
                :cols="smAndDown ? 6 : 4"
              >
                <v-btn
                  block
                  variant="flat"
                  class="asset-selector"
                  prepend-icon="mdi-file"
                  :color="openStateSelector ? 'primary' : ''"
                  :disabled="
                    !rom.user_states.some(
                      (s) => !s.emulator || s.emulator === selectedCore,
                    )
                  "
                  @click="switchStateSelector"
                >
                  {{
                    selectedState
                      ? t("play.change-state")
                      : t("play.select-state")
                  }}
                </v-btn>
                <v-expand-transition>
                  <AssetCard
                    v-if="selectedState"
                    :asset="selectedState"
                    type="state"
                    :selected="false"
                    :show-hover-actions="false"
                    :show-close-button="true"
                    :card-style="{}"
                    class="selected-card mx-1"
                    :transform-scale="false"
                    :class="{ 'disabled-card': openSaveSelector }"
                    @close="unselectState"
                  />
                </v-expand-transition>
              </v-col>
            </v-expand-transition>

            <!-- save selector -->
            <v-expand-transition>
              <v-col
                v-show="!openStateSelector || !smAndDown"
                :class="{
                  'mt-2': smAndDown,
                  'pl-1': !smAndDown,
                }"
                :cols="smAndDown ? 6 : 4"
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
                  <AssetCard
                    v-if="selectedSave"
                    :asset="selectedSave"
                    type="save"
                    :selected="false"
                    :show-hover-actions="false"
                    :show-close-button="true"
                    :card-style="{}"
                    class="selected-card mx-1"
                    :transform-scale="false"
                    :class="{ 'disabled-card': openStateSelector }"
                    @close="unselectSave"
                  />
                </v-expand-transition>
              </v-col>
            </v-expand-transition>
          </v-row>

          <!-- state display -->
          <v-expand-transition>
            <v-row v-if="openStateSelector" class="mt-2" no-gutters>
              <template v-if="rom.user_states.length > 0">
                <v-col
                  v-for="state in rom.user_states
                    .filter((s) => !s.emulator || s.emulator === selectedCore)
                    .sort((a, b) => {
                      return (
                        new Date(b.updated_at).getTime() -
                        new Date(a.updated_at).getTime()
                      );
                    })"
                  :key="state.id"
                  cols="6"
                  sm="4"
                  class="pa-1 align-self-end"
                >
                  <AssetCard
                    :asset="state"
                    type="state"
                    :selected="selectedState?.id === state.id"
                    :show-hover-actions="false"
                    :card-style="{
                      zIndex: selectedState?.id === state.id ? 11 : undefined,
                    }"
                    @click="selectState(state)"
                  />
                </v-col>
              </template>
              <v-col v-else class="pa-1 mt-1">
                <EmptyStates />
              </v-col>
            </v-row>
          </v-expand-transition>

          <!-- save display -->
          <v-expand-transition>
            <v-row v-if="openSaveSelector" class="mt-2" no-gutters>
              <template v-if="rom.user_saves.length > 0">
                <v-col
                  v-for="save in rom.user_saves.sort((a, b) => {
                    return (
                      new Date(b.updated_at).getTime() -
                      new Date(a.updated_at).getTime()
                    );
                  })"
                  :key="save.id"
                  cols="6"
                  sm="4"
                  class="pa-1 align-self-end"
                >
                  <AssetCard
                    :asset="save"
                    type="save"
                    :selected="selectedSave?.id === save.id"
                    :show-hover-actions="false"
                    @click="selectSave(save)"
                  />
                </v-col>
              </template>
              <v-col v-else class="pa-1 mt-1">
                <EmptySaves />
              </v-col>
            </v-row>
          </v-expand-transition>
        </v-col>
      </v-row>

      <!-- Action buttons -->
      <v-row class="align-center mt-4 mx-2" no-gutters>
        <v-col :class="{ 'pr-1': !smAndDown }">
          <v-btn
            block
            variant="flat"
            :append-icon="
              fullScreenOnPlay ? 'mdi-fullscreen' : 'mdi-fullscreen-exit'
            "
            :color="fullScreenOnPlay ? 'primary' : ''"
            @click="onFullScreenChange"
          >
            <v-icon class="mr-2">
              {{
                fullScreenOnPlay
                  ? "mdi-checkbox-outline"
                  : "mdi-checkbox-blank-outline"
              }} </v-icon
            >{{ t("play.full-screen") }}
          </v-btn>
        </v-col>
        <v-col :cols="smAndDown ? 12 : 8" :class="smAndDown ? 'mt-2' : 'pl-1'">
          <v-btn
            block
            variant="flat"
            class="text-primary"
            prepend-icon="mdi-play"
            @click="onPlay"
          >
            {{ t("play.play") }}
          </v-btn>
        </v-col>
      </v-row>
      <v-row class="align-center my-4 mx-2" no-gutters>
        <v-col
          :class="{ 'mt-2': smAndDown, 'pr-1': !smAndDown }"
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
          >
            {{ t("play.back-to-game-details") }}
          </v-btn>
        </v-col>
        <v-col
          :class="{ 'mt-2': smAndDown, 'pl-1': !smAndDown }"
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
          >
            {{ t("play.back-to-gallery") }}
          </v-btn>
        </v-col>
      </v-row>

      <CacheDialog />
    </v-col>

    <template v-else>
      <v-col id="game-wrapper" cols="12" class="bg-background pr-2" rounded>
        <Player
          :rom="rom"
          :state="selectedState"
          :save="selectedSave"
          :bios="selectedFirmware"
          :core="selectedCore"
          :disc="selectedDisc"
        />
      </v-col>
    </template>
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
