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
import {
  RBtn,
  RCard,
  RIcon,
  RSelect,
  RSliderBtnGroup,
  RSpinner,
  RSwitch,
} from "@v2/lib";
import { useEventListener, useLocalStorage } from "@vueuse/core";
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
import type { FirmwareSchema, SaveSchema, StateSchema } from "@/__generated__";
import firmwareApi from "@/services/api/firmware";
import romApi from "@/services/api/rom";
import socket from "@/services/socket";
import storeAuth from "@/stores/auth";
import storeConfig from "@/stores/config";
import storePlaying from "@/stores/playing";
import type { DetailedRom } from "@/stores/roms";
import type { Events } from "@/types/emitter";
import { getSupportedEJSCores } from "@/utils";
import AssetPreview from "@/v2/components/Player/AssetPreview.vue";
import AssetList from "@/v2/components/shared/AssetList.vue";
import AssetStrip from "@/v2/components/shared/AssetStrip.vue";
import GameCover from "@/v2/components/shared/GameCover.vue";
import { useCoverArt } from "@/v2/composables/useCoverArt";
import { useFullscreenPref } from "@/v2/composables/useFullscreenPref";
import { useInputModality } from "@/v2/composables/useInputModality";
import { usePlaySession } from "@/v2/composables/usePlaySession";
import { usePlayerHero } from "@/v2/composables/usePlayerHero";
import { usePlayerNav } from "@/v2/composables/usePlayerNav";
import { useUnloadGuard } from "@/v2/composables/useUnloadGuard";
import type { SliderBtnGroupItem } from "@/v2/lib/primitives/RSliderBtnGroup/types";
import {
  resolveBezelHost,
  resolveBezelUrl,
  resolveStoredBezelVisible,
} from "@/v2/utils/playerBezel";
import {
  ALL_DISCS,
  bootDiscId,
  rememberDisc,
  resolveRememberedDisc,
  type DiscSelection,
} from "@/v2/utils/playerDisc";
import { resolveInitialFirmware } from "@/v2/utils/playerFirmware";
import { installIOSFullscreenShim } from "@/views/Player/EmulatorJS/utils";
import { rememberCore, resolveRememberedCore } from "./coreStorage";
import { isJsResource, loadScript } from "./scriptLoader";

// Reuse v1's heavy emulator integration — do NOT rewrite this. Lazy so the
// bundle doesn't pull in the EJS shims until we actually mount the player.
const Player = defineAsyncComponent(
  () => import("@/views/Player/EmulatorJS/Player.vue"),
);

const { t } = useI18n();
const emitter = inject<Emitter<Events>>("emitter");
const auth = storeAuth();
const playingStore = storePlaying();
const configStore = storeConfig();
const { playing, fullScreen } = storeToRefs(playingStore);
const { fullscreenOnPlay } = useFullscreenPref();
const { modality } = useInputModality();
const playSession = usePlaySession();

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

const { romId, heroRom, title, platformLabel } = usePlayerHero(rom);
const { backToRom, backToPlatform } = usePlayerNav(
  romId,
  () => heroRom.value?.platform_id,
);
const isSavesTabSelected = ref(true);
const selectedState = ref<StateSchema | null>(null);
const selectedDisc = ref<DiscSelection>(null);
const selectedCore = ref<string | null>(null);
const selectedFirmware = ref<FirmwareSchema | null>(null);
const supportedCores = ref<string[]>([]);
const gameRunning = ref(false);
const removeIOSFullscreenShim = ref<(() => void) | null>(null);

useUnloadGuard(gameRunning);

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

const discItems = computed<{ title: string; value: DiscSelection }[]>(() => [
  { title: t("play.all-discs"), value: ALL_DISCS },
  ...(rom.value?.files ?? []).map((f) => ({
    title: f.file_name,
    value: f.id,
  })),
]);

// The hero cover is the shared GameCover (same component as gallery +
// details). We keep a lightweight `useCoverArt` here only to know whether
// the active style is alt-art, so the purple glow can be dropped for a
// floating disc / cartridge / mix image. The launch flourish is triggered
// imperatively on the GameCover via `coverRef` — see onPlay.
const art = useCoverArt(() => heroRom.value, { context: "player" });
const heroIsAlt = computed(
  () =>
    art.style.value !== "cover_path" &&
    !!(art.coverUrl.value ?? art.fallbackUrl.value),
);
const coverRef = ref<InstanceType<typeof GameCover> | null>(null);

// Scraped bezel drawn around the running game. `bezel_path` is stored relative
// to the resources folder, so prefix it like every other resource URL (#3939).
const bezelUrl = computed(() =>
  resolveBezelUrl(rom.value?.ss_metadata?.bezel_path),
);

// Per-game bezel visibility. Bezels default on, but a bad / misaligned one can
// obscure the game, so the user can hide it for this game (persisted). Keyed by
// the route param so it binds before `rom` resolves; stored as the compact "0"
// hidden / "1" shown marker (anything else fails safe to shown), and defaults
// are not written so merely opening a game leaves storage untouched.
const showBezel = useLocalStorage(`player:${romId}:bezel`, true, {
  writeDefaults: false,
  serializer: {
    read: resolveStoredBezelVisible,
    write: (visible) => (visible ? "1" : "0"),
  },
});

// When EmulatorJS enters fullscreen it promotes its own `#game` container to
// the top layer, so a bezel that is merely a sibling would disappear. Track
// that container here and teleport the bezel into it while fullscreen (#3939).
const bezelHost = ref<HTMLElement | null>(null);
useEventListener(document, "fullscreenchange", () => {
  bezelHost.value = resolveBezelHost(document.fullscreenElement);
});

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

  if (rom.value) {
    rememberCore(rom.value.id, rom.value.platform_slug, selectedCore.value);
    rememberDisc(rom.value.id, selectedDisc.value);
  }
  gameRunning.value = true;
  window.EJS_fullscreenOnLoaded = fullscreenOnPlay.value;
  fullScreen.value = fullscreenOnPlay.value;
  playing.value = true;

  const { EJS_NETPLAY_ENABLED } = configStore.config;
  const EMULATORJS_VERSION = EJS_NETPLAY_ENABLED ? "nightly" : "4.2.3";
  const LOCAL_PATH = "/assets/emulatorjs/data";
  const CDN_PATH = `https://cdn.emulatorjs.org/${EMULATORJS_VERSION}/data`;

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
    // No emulator booted, so drop back to the config screen instead of
    // leaving the unload guard and the input mute armed.
    gameRunning.value = false;
    playing.value = false;
    fullScreen.value = false;
  }
}

function selectSave(save: SaveSchema) {
  selectedSave.value = save;
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
    romId,
  });
  rom.value = romResponse.data;

  // Firmware whose file is gone can't be served, so it isn't a BIOS choice.
  const firmwareResponse = await firmwareApi.getFirmware({
    platformId: romResponse.data.platform_id,
    missing: false,
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

  // Default selection — save and state are independent, so both can be
  // armed at once. The bound save is the write-back target for "Save &
  // Quit" (PUT in place), so we only auto-bind it when the choice is
  // unambiguous: never silently pick a slot when a state is armed and
  // there are multiple saves, since loading the state injects a different
  // SRAM timeline that would overwrite an arbitrary save the user never
  // picked. In that case the user must select the save slot explicitly.
  const initiallyCompatibleStates = rom.value.user_states.filter(
    (s) => !s.emulator || s.emulator === supportedCores.value[0],
  );
  const hasCompatibleState = initiallyCompatibleStates.length > 0;

  if (hasCompatibleState) {
    selectedState.value = initiallyCompatibleStates[0];
  }
  const safeToBindSave =
    rom.value.user_saves.length === 1 || !hasCompatibleState;
  if (rom.value.user_saves.length > 0 && safeToBindSave) {
    selectedSave.value = rom.value.user_saves[0];
  }
  isSavesTabSelected.value = !hasCompatibleState;

  selectedDisc.value = resolveRememberedDisc(rom.value.id, rom.value.files);

  selectedCore.value = resolveRememberedCore(
    rom.value.id,
    rom.value.platform_slug,
    supportedCores.value,
  );

  const coreOptions = configStore.getEJSCoreOptions(selectedCore.value);
  const storedBiosID = localStorage.getItem(
    `player:${rom.value.platform_slug}:bios_id`,
  );

  selectedFirmware.value = resolveInitialFirmware({
    options: firmwareOptions.value,
    storedBiosId: storedBiosID,
    configBiosFile: coreOptions["bios_file"],
  });

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
    if (rom.value) playSession.start(rom.value);
    emitActivityStart();
    startActivityHeartbeat();
  }
  if (prev && !running) {
    playSession.flush();
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
  // the user never exited the game to the config screen first. flush() is
  // idempotent, so an exit that already flushed via the watch is a no-op.
  playSession.flush();
  stopActivityHeartbeat();
  emitActivityStop();
  // Hand the keyboard and gamepad back to the UI; the flag otherwise
  // stays true and pad/hotkey navigation is dead until a reload.
  playing.value = false;
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
  <section v-if="heroRom" class="r-v2-ejs">
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
            :rom="heroRom"
            :title="title"
            :identified="heroRom?.is_identified ?? true"
            :morph-id="romId"
            style-context="player"
            morph-static
            hover-motion
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
          :loading="!rom"
          :disabled="!rom"
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
            v-if="(rom?.files?.length ?? 0) > 1"
            v-model="selectedDisc"
            variant="outlined"
            density="comfortable"
            prepend-inner-icon="mdi-disc"
            hide-details
            :label="t('rom.file')"
            :items="discItems"
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
            :items="firmwareOptions"
            item-title="file_name"
            item-value="id"
            return-object
          />
          <RSwitch v-model="fullscreenOnPlay" :label="t('play.full-screen')" />
          <!-- Only offered when this game actually has a bezel, so the user can
               hide a bad / misaligned one that obscures the game (#3939). -->
          <RSwitch
            v-if="bezelUrl"
            v-model="showBezel"
            :label="t('play.show-bezel')"
          />
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
    <div v-else-if="rom" class="r-v2-ejs__stage">
      <Player
        :rom="rom"
        :state="selectedState"
        :save="selectedSave"
        :bios="selectedFirmware"
        :core="selectedCore"
        :disc="bootDiscId(selectedDisc)"
      />
      <!-- Bezel overlay drawn around the game canvas. Purely decorative and
           click-through, so pointer events reach the emulator underneath. In
           fullscreen it teleports into the emulator's top-layer container so it
           keeps framing the game; otherwise it renders here over the stage. -->
      <Teleport :to="bezelHost" :disabled="!bezelHost">
        <img
          v-if="bezelUrl && showBezel"
          :src="bezelUrl"
          class="r-v2-ejs__bezel"
          alt=""
          aria-hidden="true"
          draggable="false"
        />
      </Teleport>
    </div>
  </section>

  <section v-else class="r-v2-ejs__loading">
    <RSpinner :size="40" :aria-label="t('common.loading')" />
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

/* Scraped bezel framing the running game. Full-height, centred, aspect
   preserved; click-through so it never intercepts emulator input. Sits above
   the game canvas but below the EmulatorJS controls / menus (z-index 9999+),
   so the frame never hides them (matters once teleported into #game while
   fullscreen). */
.r-v2-ejs__bezel {
  position: absolute;
  inset: 0;
  margin: auto;
  height: 100%;
  width: auto;
  max-width: 100%;
  pointer-events: none;
  user-select: none;
  z-index: 2;
}

/* ── Initial ROM fetch ───────────────────────────────────── */
.r-v2-ejs__loading {
  min-height: calc(100vh - var(--r-nav-h));
  display: grid;
  place-items: center;
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
