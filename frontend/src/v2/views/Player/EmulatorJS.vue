<script setup lang="ts">
// EmulatorJS — v2 shell around the v1 <Player> component. The emulator
// integration (EJS_* globals, loader fallback, save/state sync, firmware
// resolution) is ported verbatim from `src/views/Player/EmulatorJS/Base.vue`
// so behaviour stays identical; only the chrome is v2.
//
// The running state mounts the v1 <Player> component (600 lines of EJS
// wiring — not worth rewriting). The v1 SelectSaveDialog / SelectStateDialog
// + CacheDialog are mounted in GlobalDialogs so the emitter bridge works.
import {
  RBtn,
  RCard,
  RCheckbox,
  RIcon,
  RSelect,
  RSliderBtnGroup,
} from "@v2/lib";
import { useEventListener, useLocalStorage } from "@vueuse/core";
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import {
  computed,
  defineAsyncComponent,
  inject,
  onBeforeUnmount,
  onMounted,
  ref,
  watch,
} from "vue";
import { useI18n } from "vue-i18n";
import { useRoute, useRouter } from "vue-router";
import type { FirmwareSchema, SaveSchema, StateSchema } from "@/__generated__";
import { ROUTES } from "@/plugins/router";
import firmwareApi from "@/services/api/firmware";
import romApi from "@/services/api/rom";
import storeAuth from "@/stores/auth";
import storeConfig from "@/stores/config";
import storePlaying from "@/stores/playing";
import { type DetailedRom } from "@/stores/roms";
import type { Events } from "@/types/emitter";
import { formatBytes, formatRelativeDate, getSupportedEJSCores } from "@/utils";
import { useBackgroundArt } from "@/v2/composables/useBackgroundArt";
import { useFullscreenPref } from "@/v2/composables/useFullscreenPref";
import type { SliderBtnGroupItem } from "@/v2/lib/primitives/RSliderBtnGroup/types";

// Reuse v1's heavy emulator integration — do NOT rewrite this. Lazy so the
// bundle doesn't pull in the EJS shims until we actually mount the player.
const Player = defineAsyncComponent(
  () => import("@/views/Player/EmulatorJS/Player.vue"),
);

const { t } = useI18n();
const route = useRoute();
const router = useRouter();
const emitter = inject<Emitter<Events>>("emitter");
const auth = storeAuth();
const playingStore = storePlaying();
const configStore = storeConfig();
const { playing, fullScreen } = storeToRefs(playingStore);
const { fullscreenOnPlay } = useFullscreenPref();

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

declare global {
  interface Navigator {
    keyboard: {
      lock: (keys: string[]) => Promise<void>;
      unlock: () => void;
    };
  }
}

const compatibleStates = computed(
  () =>
    rom.value?.user_states.filter(
      (s) => !s.emulator || s.emulator === selectedCore.value,
    ) ?? [],
);

const setBgArt = useBackgroundArt();

const coverUrl = computed(() => {
  const r = rom.value;
  if (!r) return null;
  return r.path_cover_large ?? r.path_cover_small ?? r.url_cover ?? null;
});

watch(
  coverUrl,
  (url) => {
    if (url) setBgArt(url);
  },
  { immediate: true },
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
  window.EJS_fullscreenOnLoaded = fullscreenOnPlay.value;
  fullScreen.value = fullscreenOnPlay.value;
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
    fullScreen.value = fullscreenOnPlay.value;
  } catch (err) {
    console.error("[Play] Emulator load failure:", err);
  }
}

function selectSave(save: SaveSchema) {
  selectedSave.value = save;
  if (selectedState.value) {
    selectedState.value = null;
    localStorage.removeItem(`player:${rom.value?.platform_slug}:state_id`);
  }
  localStorage.setItem(
    `player:${rom.value?.platform_slug}:save_id`,
    save.id.toString(),
  );
  isSavesTabSelected.value = true;
}

function unselectSave() {
  selectedSave.value = null;
  localStorage.removeItem(`player:${rom.value?.platform_slug}:save_id`);
}

function selectState(state: StateSchema) {
  selectedState.value = state;
  if (selectedSave.value) {
    selectedSave.value = null;
    localStorage.removeItem(`player:${rom.value?.platform_slug}:save_id`);
  }
  localStorage.setItem(
    `player:${rom.value?.platform_slug}:state_id`,
    state.id.toString(),
  );
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

  emitter?.on("saveSelected", selectSave);
  emitter?.on("stateSelected", selectState);

  if ("keyboard" in navigator) {
    useEventListener(document, "fullscreenchange", () => {
      if (document.fullscreenElement) {
        navigator.keyboard
          .lock(["Escape", "Tab", "AltLeft", "ControlLeft", "MetaLeft"])
          .catch(() => {});
      } else {
        navigator.keyboard.unlock();
      }
    });
  }

  // Default tab + selection (mutually exclusive).
  const initiallyCompatibleStates = rom.value.user_states.filter(
    (s) => !s.emulator || s.emulator === supportedCores.value[0],
  );

  if (initiallyCompatibleStates.length > 0) {
    isSavesTabSelected.value = false;
    selectedState.value = initiallyCompatibleStates[0];
    selectedSave.value = null;
  } else if (rom.value.user_saves.length > 0) {
    isSavesTabSelected.value = true;
    selectedSave.value = rom.value.user_saves[0];
    selectedState.value = null;
  } else {
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
    selectedCore.value = supportedCores.value[0];
  }

  const coreOptions = configStore.getEJSCoreOptions(selectedCore.value);
  const storedBiosID = localStorage.getItem(
    `player:${rom.value.platform_slug}:bios_id`,
  );

  const biosFromStorage = storedBiosID
    ? firmwareOptions.value.find((f) => f.id === parseInt(storedBiosID))
    : undefined;
  const biosFromConfig = coreOptions["bios_file"]
    ? firmwareOptions.value.find(
        (f) => f.file_name === coreOptions["bios_file"],
      )
    : undefined;
  const biosFromSingleOption =
    firmwareOptions.value.length === 1 ? firmwareOptions.value[0] : undefined;

  selectedFirmware.value =
    biosFromStorage ?? biosFromConfig ?? biosFromSingleOption ?? null;
});

onBeforeUnmount(() => {
  window.EJS_emulator?.callEvent("exit");
  emitter?.off("saveSelected", selectSave);
  emitter?.off("stateSelected", selectState);
});

function openStateDialog() {
  if (rom.value) emitter?.emit("selectStateDialog", rom.value);
}
function openSaveDialog() {
  if (rom.value) emitter?.emit("selectSaveDialog", rom.value);
}
function openCacheDialog() {
  emitter?.emit("openEmulatorJSCacheDialog", null);
}

function backToRom() {
  router.push({ name: ROUTES.ROM, params: { rom: rom.value?.id } });
}
function backToPlatform() {
  router.push({
    name: ROUTES.PLATFORM,
    params: { platform: rom.value?.platform_id },
  });
}

const title = computed(
  () => rom.value?.name || rom.value?.fs_name_no_ext || "",
);

const platformLabel = computed(
  () =>
    rom.value?.platform_custom_name || rom.value?.platform_display_name || "",
);

type AssetTab = "save" | "state";
const activeAssetTab = computed<AssetTab>(() =>
  isSavesTabSelected.value ? "save" : "state",
);

const assetTabs = computed<SliderBtnGroupItem<AssetTab>[]>(() => [
  {
    id: "save",
    label: `${t("common.saves")}${rom.value?.user_saves.length ? ` · ${rom.value.user_saves.length}` : ""}`,
    icon: "mdi-content-save",
  },
  {
    id: "state",
    label: `${t("common.states")}${compatibleStates.value.length ? ` · ${compatibleStates.value.length}` : ""}`,
    icon: "mdi-file",
  },
]);

function setAssetTab(id: AssetTab) {
  isSavesTabSelected.value = id === "save";
}

type AssetPreview = {
  kind: AssetTab;
  name: string;
  size: string;
  when: string;
  screenshot?: string | null;
};

const currentAsset = computed<AssetPreview | null>(() => {
  if (isSavesTabSelected.value) {
    const s = selectedSave.value;
    if (!s) return null;
    return {
      kind: "save",
      name: s.file_name,
      size: formatBytes(s.file_size_bytes),
      when: formatRelativeDate(s.updated_at),
    };
  }
  const st = selectedState.value;
  if (!st) return null;
  return {
    kind: "state",
    name: st.file_name,
    size: formatBytes(st.file_size_bytes),
    when: formatRelativeDate(st.updated_at),
    screenshot: st.screenshot?.download_path ?? null,
  };
});

// Ensure we don't need to touch the unused-import lint.
void useLocalStorage;
</script>

<template>
  <section v-if="rom" class="r-v2-ejs">
    <!-- Pre-game configuration -->
    <div v-if="!gameRunning" class="r-v2-ejs__config">
      <!-- Hero: cover + title + play CTA -->
      <aside class="r-v2-ejs__hero">
        <div class="r-v2-ejs__cover">
          <img
            v-if="coverUrl"
            :src="coverUrl"
            :alt="title"
            class="r-v2-ejs__cover-img"
          />
          <div v-else class="r-v2-ejs__cover-placeholder">
            {{ title }}
          </div>
          <div class="r-v2-ejs__cover-glow" aria-hidden="true" />
        </div>
        <div class="r-v2-ejs__title-block">
          <h1 class="r-v2-ejs__title">
            {{ title }}
          </h1>
          <p class="r-v2-ejs__subtitle">
            {{ platformLabel }}
          </p>
        </div>
        <RBtn
          size="x-large"
          variant="flat"
          color="primary"
          block
          prepend-icon="mdi-play"
          class="r-v2-ejs__play"
          @click="onPlay"
        >
          {{ t("play.play") }}
        </RBtn>
        <div class="r-v2-ejs__hero-links">
          <RBtn
            variant="text"
            size="small"
            prepend-icon="mdi-arrow-left"
            @click="backToRom"
          >
            {{ t("play.back-to-game-details") }}
          </RBtn>
          <RBtn
            variant="text"
            size="small"
            prepend-icon="mdi-view-grid-outline"
            @click="backToPlatform"
          >
            {{ t("play.back-to-gallery") }}
          </RBtn>
        </div>
      </aside>

      <!-- Saves / States panel -->
      <RCard class="r-v2-ejs__panel" variant="flat">
        <div class="r-v2-ejs__panel-head">
          <RSliderBtnGroup
            variant="tab"
            :model-value="activeAssetTab"
            :items="assetTabs"
            aria-label="Load save or state"
            @update:model-value="setAssetTab"
          />
        </div>

        <div class="r-v2-ejs__tab-body">
          <div v-if="currentAsset" class="r-v2-ejs__asset">
            <div
              v-if="currentAsset.screenshot"
              class="r-v2-ejs__asset-thumb"
              :style="{ backgroundImage: `url(${currentAsset.screenshot})` }"
            />
            <div
              v-else
              class="r-v2-ejs__asset-thumb r-v2-ejs__asset-thumb--placeholder"
            >
              <RIcon
                :icon="
                  currentAsset.kind === 'save'
                    ? 'mdi-content-save'
                    : 'mdi-file-outline'
                "
                size="32"
              />
            </div>
            <div class="r-v2-ejs__asset-meta">
              <p class="r-v2-ejs__asset-name" :title="currentAsset.name">
                {{ currentAsset.name }}
              </p>
              <div class="r-v2-ejs__asset-chips">
                <span class="r-v2-ejs__asset-chip">
                  <RIcon icon="mdi-clock-outline" size="12" />
                  {{ currentAsset.when }}
                </span>
                <span class="r-v2-ejs__asset-chip">
                  <RIcon icon="mdi-weight" size="12" />
                  {{ currentAsset.size }}
                </span>
              </div>
            </div>
            <button
              type="button"
              class="r-v2-ejs__asset-clear"
              :aria-label="
                currentAsset.kind === 'save'
                  ? t('play.no-save-selected')
                  : t('play.no-state-selected')
              "
              @click="
                currentAsset.kind === 'save' ? unselectSave() : unselectState()
              "
            >
              <RIcon icon="mdi-close" size="14" />
            </button>
          </div>

          <div v-else class="r-v2-ejs__empty">
            <RIcon
              :icon="
                isSavesTabSelected
                  ? 'mdi-content-save-outline'
                  : 'mdi-file-outline'
              "
              size="36"
            />
            <p>
              {{
                isSavesTabSelected
                  ? t("play.no-save-selected")
                  : t("play.no-state-selected")
              }}
            </p>
          </div>

          <RBtn
            block
            variant="translucent"
            color="primary"
            :prepend-icon="currentAsset ? 'mdi-swap-horizontal' : 'mdi-plus'"
            :disabled="
              isSavesTabSelected
                ? rom.user_saves.length === 0
                : compatibleStates.length === 0
            "
            @click="isSavesTabSelected ? openSaveDialog() : openStateDialog()"
          >
            {{
              isSavesTabSelected
                ? rom.user_saves.length === 0
                  ? t("play.no-saves-available")
                  : selectedSave
                    ? t("play.change-save")
                    : t("play.select-save")
                : compatibleStates.length === 0
                  ? t("play.no-states-available")
                  : selectedState
                    ? t("play.change-state")
                    : t("play.select-state")
            }}
          </RBtn>
        </div>
      </RCard>

      <!-- Settings panel -->
      <RCard class="r-v2-ejs__panel" variant="flat">
        <div class="r-v2-ejs__panel-head r-v2-ejs__panel-head--label">
          <RIcon icon="mdi-cog-outline" size="14" />
          <span>{{ t("common.settings") }}</span>
        </div>
        <div class="r-v2-ejs__settings">
          <RSelect
            v-if="rom.files.length > 1"
            v-model="selectedDisc"
            variant="outlined"
            density="comfortable"
            prepend-inner-icon="mdi-disc"
            clearable
            hide-details
            :label="t('rom.file')"
            :items="rom.files.map((f) => ({ title: f.file_name, value: f.id }))"
          />
          <RSelect
            v-if="supportedCores.length > 1"
            v-model="selectedCore"
            variant="outlined"
            density="comfortable"
            prepend-inner-icon="mdi-chip"
            clearable
            hide-details
            :label="t('common.core')"
            :items="supportedCores.map((c) => ({ title: c, value: c }))"
          />
          <RSelect
            v-if="firmwareOptions.length > 0"
            v-model="selectedFirmware"
            variant="outlined"
            density="comfortable"
            prepend-inner-icon="mdi-memory"
            clearable
            hide-details
            :label="t('common.firmware')"
            :items="
              firmwareOptions.map((f) => ({ title: f.file_name, value: f }))
            "
          />

          <RCheckbox
            v-model="fullscreenOnPlay"
            :label="t('play.full-screen')"
            hide-details
          />
        </div>

        <div class="r-v2-ejs__panel-foot">
          <RBtn
            variant="text"
            size="small"
            color="error"
            prepend-icon="mdi-database-remove"
            @click="openCacheDialog"
          >
            {{ t("play.clear-cache") }}
          </RBtn>
        </div>
      </RCard>

      <div class="r-v2-ejs__brand">
        <span>Powered by</span>
        <img
          src="/assets/emulatorjs/emulatorjs-logotype.svg"
          alt="EmulatorJS"
        />
      </div>
    </div>

    <!-- Running state -->
    <div v-else class="r-v2-ejs__stage">
      <Player
        :rom="rom"
        :state="selectedState"
        :save="selectedSave"
        :bios="selectedFirmware"
        :core="selectedCore"
        :disc="selectedDisc"
      />
    </div>
  </section>

  <section v-else class="r-v2-ejs__loading">
    <div class="r-v2-ejs__spinner" aria-label="Loading" />
  </section>
</template>

<style scoped>
.r-v2-ejs {
  position: relative;
  min-height: calc(100vh - var(--r-nav-h));
  padding: 32px var(--r-row-pad) 48px;
}

/* Pre-game layout — hero | saves/states | settings. */
.r-v2-ejs__config {
  display: grid;
  grid-template-columns: minmax(260px, 320px) minmax(0, 1fr) minmax(0, 1fr);
  gap: 24px;
  max-width: 1200px;
  margin: 0 auto;
  align-items: start;
}

/* Hero column — cover, title, primary Play button. */
.r-v2-ejs__hero {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 14px;
  text-align: center;
}

.r-v2-ejs__cover {
  position: relative;
  width: 100%;
  max-width: 260px;
  margin: 0 auto;
}

.r-v2-ejs__cover-glow {
  position: absolute;
  inset: 12px;
  background: radial-gradient(
    120% 120% at 50% 60%,
    color-mix(in srgb, var(--r-color-brand-primary) 35%, transparent),
    transparent 70%
  );
  filter: blur(30px);
  z-index: -1;
  pointer-events: none;
}

.r-v2-ejs__cover-img {
  width: 100%;
  border-radius: var(--r-radius-lg);
  box-shadow:
    0 18px 36px color-mix(in srgb, black 55%, transparent),
    0 0 0 1px var(--r-color-border);
  display: block;
}

.r-v2-ejs__cover-placeholder {
  width: 100%;
  aspect-ratio: 3 / 4;
  border-radius: var(--r-radius-lg);
  background: var(--r-color-cover-placeholder);
  display: grid;
  place-items: center;
  padding: 16px;
  color: var(--r-color-fg-faint);
  font-size: 13px;
  text-align: center;
}

.r-v2-ejs__title-block {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 0 4px;
}

.r-v2-ejs__eyebrow {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-size: 10px;
  font-weight: var(--r-font-weight-semibold);
  color: var(--r-color-brand-primary);
  margin-bottom: 2px;
}

.r-v2-ejs__title {
  margin: 0;
  font-size: var(--r-font-size-xl);
  font-weight: var(--r-font-weight-bold);
  line-height: 1.15;
}

.r-v2-ejs__subtitle {
  margin: 0;
  font-size: var(--r-font-size-sm);
  color: var(--r-color-fg-muted);
}

.r-v2-ejs__play {
  margin-top: 8px;
  font-weight: var(--r-font-weight-semibold) !important;
  letter-spacing: 0.02em;
  box-shadow: 0 10px 24px
    color-mix(in srgb, var(--r-color-brand-primary) 35%, transparent);
}

.r-v2-ejs__hero-links {
  display: flex;
  flex-direction: column;
  gap: 2px;
  margin-top: 4px;
}

/* Glass panels — share language with info-panel + dialog. */
.r-v2-ejs__panel {
  background: var(--r-color-bg-elevated) !important;
  border: 1px solid var(--r-color-border) !important;
  border-radius: var(--r-radius-lg) !important;
  backdrop-filter: blur(18px);
  -webkit-backdrop-filter: blur(18px);
  display: flex !important;
  flex-direction: column;
  overflow: hidden;
}

.r-v2-ejs__panel-head {
  padding: 14px 14px 0;
  display: flex;
  justify-content: center;
}
.r-v2-ejs__panel-head--label {
  justify-content: flex-start;
  gap: 8px;
  align-items: center;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  font-size: 11px;
  font-weight: var(--r-font-weight-semibold);
  color: var(--r-color-fg-secondary);
}

.r-v2-ejs__tab-body {
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 14px;
  min-height: 220px;
}

/* Asset preview card — v2-native, replaces the old v1 AssetCard. */
.r-v2-ejs__asset {
  position: relative;
  display: grid;
  grid-template-columns: 80px 1fr auto;
  gap: 12px;
  align-items: center;
  padding: 10px;
  background: var(--r-color-bg-elevated);
  border: 1px solid var(--r-color-border);
  border-radius: var(--r-radius-md);
}

.r-v2-ejs__asset-thumb {
  width: 80px;
  aspect-ratio: 4 / 3;
  border-radius: var(--r-radius-sm);
  background-size: cover;
  background-position: center;
  background-color: var(--r-color-cover-placeholder);
}
.r-v2-ejs__asset-thumb--placeholder {
  display: grid;
  place-items: center;
  color: var(--r-color-fg-muted);
}

.r-v2-ejs__asset-meta {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.r-v2-ejs__asset-name {
  margin: 0;
  font-size: 13px;
  font-weight: var(--r-font-weight-medium);
  color: var(--r-color-fg);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.r-v2-ejs__asset-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.r-v2-ejs__asset-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px;
  background: var(--r-color-bg-elevated);
  border: 1px solid var(--r-color-border);
  border-radius: var(--r-radius-pill);
  font-size: 11px;
  color: var(--r-color-fg-secondary);
}

.r-v2-ejs__asset-clear {
  appearance: none;
  border: 0;
  background: var(--r-color-surface);
  color: var(--r-color-fg-secondary);
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  cursor: pointer;
  transition:
    background var(--r-motion-fast) var(--r-motion-ease-out),
    color var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-v2-ejs__asset-clear:hover {
  background: color-mix(
    in srgb,
    var(--r-color-status-base-danger) 18%,
    transparent
  );
  color: var(--r-color-danger-fg);
}

.r-v2-ejs__empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 28px 0;
  color: var(--r-color-fg-muted);
  text-align: center;
  border: 1px dashed var(--r-color-border);
  border-radius: var(--r-radius-md);
}
.r-v2-ejs__empty p {
  margin: 0;
  font-size: 13px;
}

.r-v2-ejs__settings {
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  flex: 1;
}

.r-v2-ejs__panel-foot {
  padding: 6px 10px 10px;
  border-top: 1px solid var(--r-color-border);
  display: flex;
  justify-content: flex-start;
}

.r-v2-ejs__brand {
  grid-column: 1 / -1;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 12px;
  font-size: var(--r-font-size-xs);
  color: var(--r-color-fg-faint);
  font-style: italic;
}
.r-v2-ejs__brand img {
  height: 28px;
  opacity: 0.8;
}

/* Running state — full bleed minus the nav. */
.r-v2-ejs__stage {
  position: fixed;
  inset: var(--r-nav-h) 0 0 0;
  background: var(--r-color-canvas-bg);
  z-index: 1;
}

/* Initial ROM fetch */
.r-v2-ejs__loading {
  min-height: calc(100vh - var(--r-nav-h));
  display: grid;
  place-items: center;
}
.r-v2-ejs__spinner {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  border: 2px solid var(--r-color-surface-hover);
  border-top-color: var(--r-color-brand-primary);
  animation: r-ejs-spin 0.8s linear infinite;
}
@keyframes r-ejs-spin {
  to {
    transform: rotate(360deg);
  }
}

html[data-bp~="sm-and-down"] .r-v2-ejs__config {
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
}
html[data-bp~="sm-and-down"] .r-v2-ejs__hero {
  grid-column: 1 / -1;
  flex-direction: row;
  align-items: center;
  text-align: left;
  gap: 20px;
}
html[data-bp~="sm-and-down"] .r-v2-ejs__cover {
  max-width: 160px;
  flex-shrink: 0;
}
html[data-bp~="sm-and-down"] .r-v2-ejs__title-block {
  flex: 1;
}
html[data-bp~="sm-and-down"] .r-v2-ejs__eyebrow {
  justify-content: flex-start;
}
html[data-bp~="sm-and-down"] .r-v2-ejs__play {
  min-width: 180px;
  margin-top: 0;
}
html[data-bp~="sm-and-down"] .r-v2-ejs__hero-links {
  flex-direction: row;
  margin-left: auto;
}
html[data-bp~="xs"] .r-v2-ejs__config {
  grid-template-columns: 1fr;
}
html[data-bp~="xs"] .r-v2-ejs__hero {
  flex-direction: column;
  text-align: center;
}
html[data-bp~="xs"] .r-v2-ejs__cover {
  max-width: 200px;
}
html[data-bp~="xs"] .r-v2-ejs__eyebrow {
  justify-content: center;
}
html[data-bp~="xs"] .r-v2-ejs__hero-links {
  margin-left: 0;
  justify-content: center;
}
</style>
