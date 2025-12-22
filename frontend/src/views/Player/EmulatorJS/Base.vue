<script setup lang="ts">
import { useLocalStorage } from "@vueuse/core";
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import { computed, inject, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute } from "vue-router";
import { useDisplay } from "vuetify";
import type { FirmwareSchema, SaveSchema, StateSchema } from "@/__generated__";
import AssetCard from "@/components/common/Game/AssetCard.vue";
import GameCard from "@/components/common/Game/Card/Base.vue";
import { ROUTES } from "@/plugins/router";
import firmwareApi from "@/services/api/firmware";
import romApi from "@/services/api/rom";
import storeAuth from "@/stores/auth";
import storeConfig from "@/stores/config";
import storePlaying from "@/stores/playing";
import { type DetailedRom } from "@/stores/roms";
import type { Events } from "@/types/emitter";
import { getSupportedEJSCores } from "@/utils";
import CacheDialog from "@/views/Player/EmulatorJS/CacheDialog.vue";
import Player from "@/views/Player/EmulatorJS/Player.vue";

const { t } = useI18n();
const { xs, mdAndUp, smAndDown } = useDisplay();
const emitter = inject<Emitter<Events>>("emitter");
const route = useRoute();
const auth = storeAuth();
const playingStore = storePlaying();
const configStore = storeConfig();
const { playing, fullScreen } = storeToRefs(playingStore);
const rom = ref<DetailedRom | null>(null);
const firmwareOptions = ref<FirmwareSchema[]>([]);
const selectedSave = ref<SaveSchema | null>(null);
const isSavesTabSelected = ref(true);
const selectedState = ref<StateSchema | null>(null);
const selectedDisc = ref<number | null>(null);
const selectedCore = ref<string | null>(null);
const selectedFirmware = ref<FirmwareSchema | null>(null);
const supportedCores = ref<string[]>([]);
const gameRunning = ref(false);
const fullScreenOnPlay = useLocalStorage("emulation.fullScreenOnPlay", true);

const compatibleStates = computed(
  () =>
    rom.value?.user_states.filter(
      (s) => !s.emulator || s.emulator === selectedCore.value,
    ) ?? [],
);

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

function selectSave(save: SaveSchema) {
  selectedSave.value = save;
  // Deselect state when selecting a save (mutually exclusive)
  if (selectedState.value) {
    selectedState.value = null;
    localStorage.removeItem(`player:${rom.value?.platform_slug}:state_id`);
  }
  localStorage.setItem(
    `player:${rom.value?.platform_slug}:save_id`,
    save.id.toString(),
  );
  // Switch to saves tab
  isSavesTabSelected.value = true;
}

function unselectSave() {
  selectedSave.value = null;
  localStorage.removeItem(`player:${rom.value?.platform_slug}:save_id`);
}

function selectState(state: StateSchema) {
  selectedState.value = state;
  // Deselect save when selecting a state (mutually exclusive)
  if (selectedSave.value) {
    selectedSave.value = null;
    localStorage.removeItem(`player:${rom.value?.platform_slug}:save_id`);
  }
  localStorage.setItem(
    `player:${rom.value?.platform_slug}:state_id`,
    state.id.toString(),
  );
  // Switch to states tab
  isSavesTabSelected.value = false;
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

  // Listen for save/state selection from dialogs
  emitter?.on("saveSelected", selectSave);
  emitter?.on("stateSelected", selectState);

  // Determine default tab and selection (mutually exclusive)
  const compatibleStates = rom.value.user_states.filter(
    (s) => !s.emulator || s.emulator === supportedCores.value[0],
  );

  if (compatibleStates.length > 0) {
    // If there are states, default to states tab with first state
    isSavesTabSelected.value = false;
    selectedState.value = compatibleStates[0];
    selectedSave.value = null;
  } else if (rom.value.user_saves.length > 0) {
    // If no states but there are saves, default to saves tab with first save
    isSavesTabSelected.value = true;
    selectedSave.value = rom.value.user_saves[0];
    selectedState.value = null;
  } else {
    // No saves or states, default to saves tab
    isSavesTabSelected.value = true;
    selectedSave.value = null;
    selectedState.value = null;
  }

  const storedDisc = localStorage.getItem(`player:${rom.value.id}:disc`);
  if (storedDisc) {
    selectedDisc.value = parseInt(storedDisc);
  } else {
    selectedDisc.value = rom.value.files[0]?.id ?? null;
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

  const storedBiosID = localStorage.getItem(
    `player:${rom.value.platform_slug}:bios_id`,
  );
  if (storedBiosID) {
    selectedFirmware.value =
      firmwareOptions.value.find((f) => f.id === parseInt(storedBiosID)) ??
      null;
  }
});

onBeforeUnmount(async () => {
  window.EJS_emulator?.callEvent("exit");
  emitter?.off("saveSelected", selectSave);
  emitter?.off("stateSelected", selectState);
});

function openStateDialog() {
  if (rom.value) {
    emitter?.emit("selectStateDialog", rom.value);
  }
}

function openSaveDialog() {
  if (rom.value) {
    emitter?.emit("selectSaveDialog", rom.value);
  }
}

function openCacheDialog() {
  emitter?.emit("openEmulatorJSCacheDialog", null);
}
</script>

<template>
  <v-row
    v-if="rom"
    class="align-center justify-center scroll h-100 px-4"
    no-gutters
  >
    <v-col v-if="!gameRunning" cols="12" lg="8">
      <v-row class="mt-4" no-gutters>
        <!-- Game Info -->
        <v-col class="game-info-col">
          <v-container :width="220" class="pa-0 text-wrap text-center mb-6">
            <GameCard
              :key="rom.updated_at"
              :rom="rom"
              :show-platform-icon="false"
              :show-action-bar="false"
            />
          </v-container>
        </v-col>

        <!-- Saves & States -->
        <v-col
          class="flex-col"
          :class="{ 'pr-2': !xs, 'mb-4': smAndDown, 'pl-4': mdAndUp }"
        >
          <v-card variant="flat" rounded="lg">
            <v-tabs
              v-model="isSavesTabSelected"
              bg-color="transparent"
              color="primary"
              grow
            >
              <v-tab :value="true">
                <v-icon start>mdi-content-save</v-icon>
                {{ t("common.saves") }}
                <v-badge
                  v-if="rom.user_saves.length > 0"
                  :content="rom.user_saves.length"
                  color="primary"
                  inline
                  class="ml-2"
                />
              </v-tab>
              <v-tab :value="false">
                <v-icon start>mdi-file</v-icon>
                {{ t("common.states") }}
                <v-badge
                  v-if="compatibleStates.length > 0"
                  :content="compatibleStates.length"
                  color="primary"
                  inline
                  class="ml-2"
                />
              </v-tab>
            </v-tabs>

            <v-divider />

            <v-card-text class="pa-4" style="min-height: 200px">
              <!-- Saves Tab Content -->
              <div v-show="isSavesTabSelected">
                <!-- Selected Save Preview -->
                <div v-if="selectedSave" class="mb-3">
                  <AssetCard
                    :asset="selectedSave"
                    type="save"
                    :show-hover-actions="false"
                    :show-close-button="true"
                    :transform-scale="false"
                    @close="unselectSave"
                  />
                </div>

                <!-- No Save Selected Message -->
                <div v-else class="text-center py-8">
                  <v-icon size="48" color="medium-emphasis"
                    >mdi-content-save-outline</v-icon
                  >
                  <p class="text-body-2 text-medium-emphasis mt-2">
                    {{ t("play.no-save-selected") }}
                  </p>
                </div>

                <!-- Select Save Button -->
                <v-btn
                  block
                  variant="tonal"
                  color="primary"
                  :prepend-icon="
                    selectedSave ? 'mdi-swap-horizontal' : 'mdi-plus'
                  "
                  :disabled="rom.user_saves.length == 0"
                  @click="openSaveDialog"
                >
                  {{
                    selectedSave ? t("play.change-save") : t("play.select-save")
                  }}
                </v-btn>
              </div>

              <!-- States Tab Content -->
              <div v-show="!isSavesTabSelected">
                <!-- Selected State Preview -->
                <div v-if="selectedState" class="mb-3">
                  <AssetCard
                    :asset="selectedState"
                    type="state"
                    :show-hover-actions="false"
                    :show-close-button="true"
                    :transform-scale="false"
                    @close="unselectState"
                  />
                </div>

                <!-- No State Selected Message -->
                <div v-else class="text-center py-8">
                  <v-icon size="48" color="medium-emphasis"
                    >mdi-file-outline</v-icon
                  >
                  <p class="text-body-2 text-medium-emphasis mt-2">
                    {{ t("play.no-state-selected") }}
                  </p>
                </div>

                <!-- Select State Button -->
                <v-btn
                  block
                  variant="tonal"
                  color="primary"
                  :prepend-icon="
                    selectedState ? 'mdi-swap-horizontal' : 'mdi-plus'
                  "
                  :disabled="
                    !rom.user_states.some(
                      (s) => !s.emulator || s.emulator === selectedCore,
                    )
                  "
                  @click="openStateDialog"
                >
                  {{
                    selectedState
                      ? t("play.change-state")
                      : t("play.select-state")
                  }}
                </v-btn>
              </div>
            </v-card-text>
          </v-card>
        </v-col>

        <!-- Settings & Actions -->
        <v-col class="flex-col" :class="{ 'pl-2': !smAndDown }">
          <v-card variant="flat" rounded="lg" class="mb-6">
            <v-card-text class="pa-3">
              <!-- Configuration Section -->
              <!-- Disc Selector -->
              <v-select
                v-if="rom.has_multiple_files"
                v-model="selectedDisc"
                class="mb-3"
                hide-details
                variant="outlined"
                density="comfortable"
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

              <!-- Core Selector -->
              <v-select
                v-if="supportedCores.length > 1"
                v-model="selectedCore"
                class="mb-3"
                hide-details
                variant="outlined"
                prepend-inner-icon="mdi-chip"
                density="comfortable"
                clearable
                :label="t('common.core')"
                :items="
                  supportedCores.map((c) => ({
                    title: c,
                    value: c,
                  }))
                "
              />

              <!-- BIOS Selector -->
              <v-select
                v-if="firmwareOptions.length > 0"
                v-model="selectedFirmware"
                hide-details
                variant="outlined"
                density="comfortable"
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

              <v-divider
                v-if="
                  rom.has_multiple_files ||
                  supportedCores.length > 1 ||
                  firmwareOptions.length > 0
                "
                class="my-4"
              />

              <!-- Action Buttons -->

              <!-- Fullscreen Toggle -->
              <v-btn
                block
                variant="tonal"
                class="mb-2"
                :color="fullScreenOnPlay ? 'primary' : ''"
                @click="onFullScreenChange"
              >
                <v-icon class="mr-2">
                  {{
                    fullScreenOnPlay
                      ? "mdi-checkbox-outline"
                      : "mdi-checkbox-blank-outline"
                  }}
                </v-icon>
                {{ t("play.full-screen") }}
                <v-icon class="ml-auto">
                  {{
                    fullScreenOnPlay ? "mdi-fullscreen" : "mdi-fullscreen-exit"
                  }}
                </v-icon>
              </v-btn>

              <!-- Play Button -->
              <v-btn
                block
                size="large"
                variant="flat"
                color="primary"
                class="mb-3 play-button"
                prepend-icon="mdi-play-circle"
                @click="onPlay"
              >
                <span class="text-h6">{{ t("play.play") }}</span>
              </v-btn>

              <!-- Navigation Buttons -->
              <v-btn
                block
                variant="text"
                size="small"
                class="mb-2"
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
                variant="text"
                size="small"
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

              <v-btn
                block
                class="text-romm-red mt-6"
                variant="flat"
                prepend-icon="mdi-database-remove"
                @click="openCacheDialog"
              >
                {{ t("play.clear-cache") }}
              </v-btn>
            </v-card-text>
          </v-card>
        </v-col>
      </v-row>

      <v-row class="mb-8" no-gutters>
        <v-col class="text-right align-center">
          <span class="text-medium-emphasis text-caption font-italic mr-2"
            >Powered by emulatorjs</span
          >
          <v-avatar size="50" rounded="0">
            <v-img src="/assets/emulatorjs/emulatorjs-logotype.svg" />
          </v-avatar>
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

.play-button {
  position: relative;
  overflow: hidden;
  font-weight: 600;
  letter-spacing: 0.5px;
}

.game-info-col {
  flex: 0 0 220px;
  max-width: 220px;
}

.flex-col {
  flex: 1 1 0;
  min-width: 0;
}

.play-button::before {
  content: "";
  position: absolute;
  top: 50%;
  left: 50%;
  width: 0;
  height: 0;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.15);
  transform: translate(-50%, -50%);
  transition:
    width 0.5s,
    height 0.5s;
}

.play-button:hover::before {
  width: 600px;
  height: 300px;
}

.play-button:hover {
  box-shadow: 0 6px 20px rgba(var(--v-theme-primary), 0.3);
}

/* Tab styling improvements */
.v-tabs :deep(.v-tab) {
  text-transform: none;
  letter-spacing: 0.25px;
  font-weight: 500;
}

.v-tabs :deep(.v-tab--selected) {
  color: rgb(var(--v-theme-primary));
}

/* Smooth fade transitions */
.v-expand-transition-enter-active,
.v-expand-transition-leave-active {
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

@media (max-width: 960px) {
  .game-info-col,
  .flex-col {
    flex: 1 1 100%;
    max-width: 100%;
  }
}
</style>
