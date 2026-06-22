<script setup lang="ts">
// EmulatorJS — v2 shell around the v1 <Player> component. The emulator
// integration (EJS_* globals, loader fallback, save/state sync, firmware
// resolution) is ported verbatim from `src/views/Player/EmulatorJS/Base.vue`
// so behaviour stays identical; only the chrome is v2.
//
// Layout — three columns:
//   1. Hero: cover + title + Play CTA + back links.
//   2. Resume: tabs (Saves/States), big <AssetPreview> of the selected
//      asset, and an <AssetStrip> below to swap between options inline.
//   3. Setup: disc / core / firmware + fullscreen + clear-cache.
//
// The running state mounts the v1 <Player> component (600 lines of EJS
// wiring — not worth rewriting). The v1 SelectSaveDialog / SelectStateDialog
// + CacheDialog are mounted in GlobalDialogs so the emitter bridge works.
import { RBtn, RCard, RIcon, RSelect, RSliderBtnGroup, RSwitch } from "@v2/lib";
import { useEventListener } from "@vueuse/core";
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import {
  computed,
  defineAsyncComponent,
  inject,
  nextTick,
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
import socket from "@/services/socket";
import storeAuth from "@/stores/auth";
import storeConfig from "@/stores/config";
import storePlaying from "@/stores/playing";
import storeRoms, { type DetailedRom } from "@/stores/roms";
import type { Events } from "@/types/emitter";
import { getSupportedEJSCores } from "@/utils";
import AssetPreview from "@/v2/components/Player/AssetPreview.vue";
import AssetList from "@/v2/components/shared/AssetList.vue";
import AssetStrip from "@/v2/components/shared/AssetStrip.vue";
import GameCover from "@/v2/components/shared/GameCover.vue";
import { useBackgroundArt } from "@/v2/composables/useBackgroundArt";
import { useCoverArt } from "@/v2/composables/useCoverArt";
import { useFullscreenPref } from "@/v2/composables/useFullscreenPref";
import { useInputModality } from "@/v2/composables/useInputModality";
import type { SliderBtnGroupItem } from "@/v2/lib/primitives/RSliderBtnGroup/types";
import { installIOSFullscreenShim } from "@/views/Player/EmulatorJS/utils";

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
const { modality } = useInputModality();

// Ref the Play CTA so we can imperatively focus it on enter (and again
// when the user comes back from a running session). RBtn forwards to
// its rendered <button>/<a>, but resolving the DOM node via a class
// query is simpler and survives the lazy-load of the inner element.
function focusPlayButton() {
  const btn = document.querySelector<HTMLElement>(".r-v2-ejs__play");
  btn?.focus({ preventScroll: true });
}

const rom = ref<DetailedRom | null>(null);
const firmwareOptions = ref<FirmwareSchema[]>([]);
const selectedSave = ref<SaveSchema | null>(null);

// Rom id straight from the route param (available before `rom` resolves),
// so the hero cover paints its `view-transition-name` immediately and the
// shared-element morph from the gallery / details cover pairs on entry.
const morphRomId = computed(() => {
  const r = route.params.rom;
  return typeof r === "string" ? r : null;
});

// Seed the rom synchronously from the store (set by GameDetails / not
// cleared on its unmount) so the hero cover is already in the DOM when the
// view transition captures this view — the morph from the details / gallery
// cover then pairs on entry. `onMounted` refetches the full payload.
const seededRom = storeRoms().currentRom;
if (seededRom && String(seededRom.id) === morphRomId.value) {
  rom.value = seededRom;
}
const isSavesTabSelected = ref(true);
const selectedState = ref<StateSchema | null>(null);
const selectedDisc = ref<number | null>(null);
const selectedCore = ref<string | null>(null);
const selectedFirmware = ref<FirmwareSchema | null>(null);
const supportedCores = ref<string[]>([]);
const gameRunning = ref(false);
const removeIOSFullscreenShim = ref<(() => void) | null>(null);

// ── Live activity ("now playing") ──────────────────────────────────
const ACTIVITY_HEARTBEAT_MS = 30_000;
let activityHeartbeatTimer: ReturnType<typeof setInterval> | null = null;

function activityDeviceId(): string {
  return auth.user?.current_device_id ?? "web";
}

function emitActivityStart() {
  if (!auth.user || !rom.value) return;
  if (!socket.connected) socket.connect();
  socket.emit("activity:start", {
    rom_id: rom.value.id,
    device_id: activityDeviceId(),
  });
}

function emitActivityHeartbeat() {
  if (!auth.user || !rom.value) return;
  socket.emit("activity:heartbeat", {
    rom_id: rom.value.id,
    device_id: activityDeviceId(),
  });
}

function emitActivityStop() {
  if (!auth.user) return;
  socket.emit("activity:stop", {
    device_id: activityDeviceId(),
  });
}

function startActivityHeartbeat() {
  if (activityHeartbeatTimer) return;
  activityHeartbeatTimer = setInterval(
    emitActivityHeartbeat,
    ACTIVITY_HEARTBEAT_MS,
  );
}

function stopActivityHeartbeat() {
  if (activityHeartbeatTimer) {
    clearInterval(activityHeartbeatTimer);
    activityHeartbeatTimer = null;
  }
}

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

// The hero cover is the shared GameCover (same component as gallery +
// details). We keep a lightweight `useCoverArt` here only to know whether
// the active style is alt-art, so the purple glow can be dropped for a
// floating disc / cartridge / mix image. The launch flourish is triggered
// imperatively on the GameCover via `coverRef` — see onPlay.
const art = useCoverArt(() => rom.value);
const heroIsAlt = computed(
  () =>
    art.style.value !== "cover_path" &&
    !!(art.coverUrl.value ?? art.fallbackUrl.value),
);
const coverRef = ref<InstanceType<typeof GameCover> | null>(null);

// Background art keeps the plain 2D cover — a blurred disc / cartridge
// reads poorly as a full-bleed backdrop.
const bgCoverUrl = computed(() => {
  const r = rom.value;
  if (!r) return null;
  return r.path_cover_large ?? r.path_cover_small ?? r.url_cover ?? null;
});

watch(
  bgCoverUrl,
  (url) => {
    if (url) setBgArt(url);
  },
  { immediate: true },
);

async function onPlay() {
  // Launch flourish on the visible cover (disc drop+spin / cartridge
  // slot-in) before booting, so the insert is seen. Returns 0 for non-
  // physical styles / reduced motion → no delay.
  const insertMs = coverRef.value?.playLoad() ?? 0;
  if (insertMs > 0) {
    await new Promise((resolve) => setTimeout(resolve, insertMs));
  }

  removeIOSFullscreenShim.value?.();
  removeIOSFullscreenShim.value = installIOSFullscreenShim();

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

  // The Vite dev server (and many SPA hosts) returns 200 + index.html
  // when a static asset is missing. A <script> tag happily "loads" that
  // — onload fires, the promise resolves — and only later the parser
  // throws `Unexpected token '<'` as an uncaught error, so our CDN
  // fallback never runs. Pre-flight the URL to make sure the body is
  // actually JS before injecting the script tag.
  async function isJsResource(url: string): Promise<boolean> {
    try {
      const res = await fetch(url);
      if (!res.ok) return false;
      const ct = res.headers.get("content-type") ?? "";
      if (/javascript|ecmascript/i.test(ct)) return true;
      if (/text\/html/i.test(ct)) return false;
      // Content-Type may be absent (older servers); sniff the body.
      const text = await res.clone().text();
      return !text.trimStart().startsWith("<");
    } catch {
      return false;
    }
  }

  async function attemptLoad(path: string) {
    const loaderUrl = `${path}/loader.js`;
    if (!(await isJsResource(loaderUrl))) {
      throw new Error(`Loader at ${loaderUrl} did not return JavaScript`);
    }
    window.EJS_pathtodata = path;
    await loadScript(loaderUrl);
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
    removeIOSFullscreenShim.value?.();
    removeIOSFullscreenShim.value = null;
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
  window.addEventListener("gamepad:buttondown", onGamepadButton);

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

  // Autofocus the Play CTA so gamepad/keyboard users land on the
  // primary action without an extra Tab. Mouse / touch keep the
  // default no-autofocus behaviour.
  if (modality.value === "pad" || modality.value === "key") {
    await nextTick();
    focusPlayButton();
  }
});

// Drive the live-activity lifecycle off the deterministic running state:
// announce on enter, clear + stop heartbeats on exit. Also restores focus
// to Play on exit so a Start-Play loop stays on the pad.
watch(gameRunning, (running, prev) => {
  if (running && !prev) {
    emitActivityStart();
    startActivityHeartbeat();
  }
  if (prev && !running) {
    stopActivityHeartbeat();
    emitActivityStop();
    nextTick(focusPlayButton);
  }
});

// Y toggles the saves/states tab — view-local binding wired through
// the `gamepad:buttondown` window event dispatched by useGamepad.
function onGamepadButton(e: CustomEvent<{ name?: string }>) {
  if (e.detail?.name !== "y") return;
  if (gameRunning.value) return;
  setAssetTab(activeAssetTab.value === "save" ? "state" : "save");
}

onBeforeUnmount(() => {
  // Leaving the player (back nav / route change) ends the session even if
  // the user never exited the game to the config screen first.
  stopActivityHeartbeat();
  emitActivityStop();
  window.EJS_emulator?.callEvent("exit");
  removeIOSFullscreenShim.value?.();
  removeIOSFullscreenShim.value = null;
  emitter?.off("saveSelected", selectSave);
  emitter?.off("stateSelected", selectState);
  window.removeEventListener("gamepad:buttondown", onGamepadButton);
});

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
    label: t("common.saves"),
    badge: rom.value?.user_saves.length ?? 0,
    icon: "mdi-content-save",
  },
  {
    id: "state",
    label: t("common.states"),
    badge: compatibleStates.value.length,
    icon: "mdi-file",
  },
]);

function setAssetTab(id: AssetTab) {
  isSavesTabSelected.value = id === "save";
}

function pickAsset(asset: SaveSchema | StateSchema) {
  if (isSavesTabSelected.value) selectSave(asset as SaveSchema);
  else selectState(asset as StateSchema);
}

function clearSelectedAsset() {
  if (isSavesTabSelected.value) unselectSave();
  else unselectState();
}

const activeAssets = computed<(SaveSchema | StateSchema)[]>(() =>
  isSavesTabSelected.value
    ? (rom.value?.user_saves ?? [])
    : compatibleStates.value,
);

const selectedAssetId = computed(() =>
  isSavesTabSelected.value
    ? (selectedSave.value?.id ?? null)
    : (selectedState.value?.id ?? null),
);

const selectedAsset = computed<SaveSchema | StateSchema | null>(() =>
  isSavesTabSelected.value ? selectedSave.value : selectedState.value,
);
</script>

<template>
  <section v-if="rom" class="r-v2-ejs">
    <!-- Pre-game configuration -->
    <div v-if="!gameRunning" class="r-v2-ejs__config">
      <!-- Hero: cover + title + Play CTA -->
      <RCard class="r-v2-ejs__panel r-v2-ejs__hero" variant="flat">
        <div
          class="r-v2-ejs__cover"
          :class="{ 'r-v2-ejs__cover--alt-art': heroIsAlt }"
        >
          <GameCover
            ref="coverRef"
            class="r-v2-ejs__cover-box"
            :rom="rom"
            :title="title"
            :identified="rom?.is_identified ?? true"
            :morph-id="morphRomId"
            morph-static
          />
          <div class="r-v2-ejs__cover-glow" aria-hidden="true" />
        </div>
        <div class="r-v2-ejs__title-block">
          <h1 class="r-v2-ejs__title">{{ title }}</h1>
          <p class="r-v2-ejs__subtitle">{{ platformLabel }}</p>
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
      </RCard>

      <!-- Resume: tabs + preview + horizontal strip -->
      <RCard class="r-v2-ejs__panel r-v2-ejs__resume" variant="flat">
        <div class="r-v2-ejs__panel-head">
          <RSliderBtnGroup
            variant="tab"
            :model-value="activeAssetTab"
            :items="assetTabs"
            :aria-label="t('rom.load-save-or-state')"
            @update:model-value="setAssetTab"
          />
        </div>

        <div class="r-v2-ejs__resume-body">
          <AssetPreview
            :asset="selectedAsset"
            :type="activeAssetTab"
            @clear="clearSelectedAsset"
          />

          <div
            v-if="activeAssets.length > 0"
            class="r-v2-ejs__strip-label"
            aria-hidden="true"
          >
            <span>{{
              activeAssetTab === "save"
                ? t("play.all-saves")
                : t("play.all-states")
            }}</span>
            <span class="r-v2-ejs__strip-count">{{ activeAssets.length }}</span>
          </div>

          <!-- Saves render as a vertical list (no screenshot ⇒ density);
               states keep the horizontal tile strip (screenshot is the
               point). -->
          <AssetList
            v-if="activeAssetTab === 'save'"
            :assets="activeAssets"
            type="save"
            :selected-id="selectedAssetId"
            @select="pickAsset"
          />
          <AssetStrip
            v-else
            :assets="activeAssets"
            type="state"
            :selected-id="selectedAssetId"
            @select="pickAsset"
          />
        </div>
      </RCard>

      <!-- Setup: disc / core / firmware / fullscreen / clear cache -->
      <RCard class="r-v2-ejs__panel r-v2-ejs__setup" variant="flat">
        <div class="r-v2-ejs__panel-head r-v2-ejs__panel-head--label">
          <RIcon icon="mdi-cog-outline" size="14" />
          <span>{{ t("common.settings") }}</span>
        </div>
        <div class="r-v2-ejs__setup-body">
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
          <RSwitch v-model="fullscreenOnPlay" :label="t('play.full-screen')" />
        </div>
        <div class="r-v2-ejs__setup-foot">
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
        <span>{{ t("play.powered-by") }}</span>
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
    <div class="r-v2-ejs__spinner" :aria-label="t('common.loading')" />
  </section>
</template>

<style scoped>
.r-v2-ejs {
  position: relative;
  min-height: calc(100vh - var(--r-nav-h));
  padding: 32px var(--r-row-pad) 48px;
}

/* Pre-game layout — hero | resume | setup. The resume column owns
   most of the visual weight because the user's primary question is
   "which save/state am I about to resume from?". */
.r-v2-ejs__config {
  display: grid;
  grid-template-columns: minmax(240px, 280px) minmax(0, 1.4fr) minmax(
      220px,
      240px
    );
  gap: 20px;
  max-width: 1280px;
  margin: 0 auto;
  align-items: stretch;
}

/* Shared glass-panel skin — single visual vocabulary across panels. */
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

/* ── Hero column ─────────────────────────────────────────── */
.r-v2-ejs__hero {
  padding: 16px;
  gap: 12px;
  text-align: center;
}

/* Wrapper: positions the cover + its glow. NOT clipped, so the glow halo
   can bleed beyond the cover (GameCover clips the launch drop itself). */
.r-v2-ejs__cover {
  position: relative;
  width: 100%;
  max-width: 220px;
  margin: 0 auto;
}
.r-v2-ejs__cover-box {
  --r-cover-radius: var(--r-radius-md);
}
/* 2D cover keeps the framed look (drop shadow + hairline ring). */
.r-v2-ejs__cover:not(.r-v2-ejs__cover--alt-art) .r-v2-ejs__cover-box {
  box-shadow:
    0 18px 36px color-mix(in srgb, black 55%, transparent),
    0 0 0 1px var(--r-color-border);
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
/* Alt-art (disc / cartridge / 3D / mix) floats free — no frame, no glow.
   The glow stays for the procedural placeholder (no cover), which keeps
   `heroIsAlt` false. */
.r-v2-ejs__cover--alt-art .r-v2-ejs__cover-glow {
  display: none;
}

.r-v2-ejs__title-block {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 4px 4px 0;
}
.r-v2-ejs__title {
  margin: 0;
  font-size: var(--r-font-size-lg);
  font-weight: var(--r-font-weight-bold);
  line-height: 1.2;
}
.r-v2-ejs__subtitle {
  margin: 0;
  font-size: var(--r-font-size-sm);
  color: var(--r-color-fg-muted);
}

.r-v2-ejs__play {
  margin-top: 4px;
  font-weight: var(--r-font-weight-semibold) !important;
  letter-spacing: 0.02em;
  box-shadow: 0 10px 24px
    color-mix(in srgb, var(--r-color-brand-primary) 35%, transparent);
}
.r-v2-ejs__hero-links {
  display: flex;
  flex-direction: column;
  gap: 0;
  margin-top: auto;
  padding-top: 6px;
  border-top: 1px solid var(--r-color-border);
}

/* ── Resume column ───────────────────────────────────────── */
.r-v2-ejs__resume {
  min-height: 420px;
}
.r-v2-ejs__resume-body {
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 14px;
  flex: 1;
}
.r-v2-ejs__strip-label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 10px;
  font-weight: var(--r-font-weight-semibold);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--r-color-fg-secondary);
  margin-top: 4px;
}
.r-v2-ejs__strip-count {
  display: inline-grid;
  place-items: center;
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  background: var(--r-color-surface);
  border-radius: var(--r-radius-pill);
  font-size: 10px;
  font-weight: var(--r-font-weight-semibold);
  color: var(--r-color-fg-secondary);
}

/* ── Setup column ────────────────────────────────────────── */
.r-v2-ejs__setup-body {
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  flex: 1;
}
.r-v2-ejs__setup-foot {
  border-top: 1px solid var(--r-color-border);
  padding: 6px 10px 10px;
}

/* ── Footer brand ────────────────────────────────────────── */
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

/* ── Running state ───────────────────────────────────────── */
.r-v2-ejs__stage {
  position: fixed;
  inset: var(--r-nav-h) 0 0 0;
  background: var(--r-color-canvas-bg);
  z-index: 1;
}

/* ── Initial ROM fetch ───────────────────────────────────── */
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

/* ── Responsive ──────────────────────────────────────────── */
html[data-bp~="md-and-down"] .r-v2-ejs__config {
  grid-template-columns: minmax(220px, 260px) minmax(0, 1fr);
}
html[data-bp~="md-and-down"] .r-v2-ejs__setup {
  grid-column: 1 / -1;
}
html[data-bp~="md-and-down"] .r-v2-ejs__setup-body {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 10px;
}

html[data-bp~="sm-and-down"] .r-v2-ejs__config {
  grid-template-columns: 1fr;
}
html[data-bp~="sm-and-down"] .r-v2-ejs__hero {
  flex-direction: row;
  flex-wrap: wrap;
  text-align: left;
  align-items: center;
}
html[data-bp~="sm-and-down"] .r-v2-ejs__cover {
  max-width: 130px;
  flex-shrink: 0;
}
html[data-bp~="sm-and-down"] .r-v2-ejs__title-block {
  flex: 1;
}
html[data-bp~="sm-and-down"] .r-v2-ejs__play {
  flex: 1 1 100%;
}
html[data-bp~="sm-and-down"] .r-v2-ejs__hero-links {
  flex: 1 1 100%;
  flex-direction: row;
  border-top: 1px solid var(--r-color-border);
  padding-top: 4px;
}
</style>
