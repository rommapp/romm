<script setup lang="ts">
// Ruffle: v2 shell for Flash ROMs. The Ruffle injection (script loader,
// createPlayer, fullscreen) is ported verbatim from
// `src/views/Player/RuffleRS/Base.vue` so playback stays identical; only the
// chrome is v2. No shared state with EJS: Flash has its own config.
import { RIcon, RSwitch } from "@v2/lib";
import { useEventListener, useIntervalFn } from "@vueuse/core";
import { nextTick, onBeforeUnmount, onMounted, ref, shallowRef } from "vue";
import { useI18n } from "vue-i18n";
import { onBeforeRouteLeave } from "vue-router";
import romApi from "@/services/api/rom";
import { AUTOSAVE_SLOT } from "@/services/api/save";
import storeAuth from "@/stores/auth";
import type { DetailedRom } from "@/stores/roms";
import type { RuffleSourceAPI } from "@/types/ruffle";
import { getDownloadPath } from "@/utils";
import PlayerShell from "@/v2/components/Player/PlayerShell.vue";
import { useConfirm } from "@/v2/composables/useConfirm";
import { useFullscreenFallback } from "@/v2/composables/useFullscreenFallback";
import { useFullscreenPref } from "@/v2/composables/useFullscreenPref";
import { useIsAlive } from "@/v2/composables/useIsAlive";
import { usePlaySession } from "@/v2/composables/usePlaySession";
import { usePlayerExit } from "@/v2/composables/usePlayerExit";
import { usePlayerHero } from "@/v2/composables/usePlayerHero";
import { usePlayingWhile } from "@/v2/composables/useStageActive";
import { useUnloadGuard } from "@/v2/composables/useUnloadGuard";
import { colorCanvas } from "@/v2/tokens";
import {
  readRuffleSaves,
  removeRuffleSaves,
  swfStoragePath,
  unzipRuffleSaves,
  writeRuffleSaves,
  zipRuffleSaves,
  type RuffleSaves,
} from "@/v2/utils/ruffleSaves";
import { DeviceSaveSync, type PlayerSaveFile } from "@/v2/utils/saveSync";

const RUFFLE_VERSION = "0.2.0-nightly.2025.8.14";
const DEFAULT_BACKGROUND_COLOR = colorCanvas.bgDeep;
const RUFFLE_EMULATOR = "ruffle";
// A game writes a SharedObject whenever it flushes one, so storage is polled.
const SAVE_POLL_MS = 5000;

type RufflePlayer = ReturnType<RuffleSourceAPI["createPlayer"]>;

const { t } = useI18n();
const { fullscreenOnPlay } = useFullscreenPref();
useFullscreenFallback();
const playSession = usePlaySession();
const authStore = storeAuth();
const exit = usePlayerExit();
const confirm = useConfirm();
const alive = useIsAlive();

const rom = shallowRef<DetailedRom | null>(null);
const gameRunning = ref(false);
const quitting = ref(false);
// Flash games are keyboard-driven, so hotkeys and pad navigation stay muted.
usePlayingWhile(gameRunning);
const backgroundColor = ref<string>(DEFAULT_BACKGROUND_COLOR);

useUnloadGuard(gameRunning);

declare global {
  interface Window {
    RufflePlayer: {
      version: string;
      newestSourceName: () => string | null;
      init: () => void;
      newest: () => RuffleSourceAPI | null;
      satisfying: (requirementString: string) => RuffleSourceAPI | null;
      localCompatible: () => RuffleSourceAPI | null;
      local: () => RuffleSourceAPI | null;
      superseded: () => void;
    };
  }
}

window.RufflePlayer = window.RufflePlayer || {};

const { romId, heroRom, title, platformLabel } = usePlayerHero(rom);

let player: RufflePlayer | null = null;
let swfUrl = "";
let saveSync: DeviceSaveSync | null = null;
let pushing: Promise<boolean> | null = null;
const host = window.location.hostname;

// Nothing is running, so drop the guard and the input mute the launch armed.
function abortPlay() {
  gameRunning.value = false;
}

function storedSaves(): RuffleSaves {
  return readRuffleSaves(host, swfStoragePath(swfUrl));
}

// Every SharedObject a game wrote travels as one zip in the autosave slot.
function saveFileOf(target: DetailedRom, saves: RuffleSaves): PlayerSaveFile {
  return {
    slot: AUTOSAVE_SLOT,
    fileName: `${target.fs_name_no_ext}.sol.zip`,
    bytes: zipRuffleSaves(saves),
    updatedAt: Date.now(),
  };
}

async function captureSaves(sync: DeviceSaveSync, target: DetailedRom) {
  const saves = storedSaves();
  if (Object.keys(saves).length > 0) {
    await sync.capture([saveFileOf(target, saves)]);
  }
}

// Storage is shared by every RomM account in the browser, so a game's saves
// live there only while it runs: synced in before, and taken back out after.
async function prepareSaves(target: DetailedRom) {
  const userId = authStore.user?.id;
  if (userId == null) return;
  const sync = new DeviceSaveSync(target, userId, RUFFLE_EMULATOR);
  // Left behind by a page that went away mid-game, or from before sync.
  const leftover = storedSaves();
  try {
    const saves = await sync.prepare(
      Object.keys(leftover).length > 0 ? [saveFileOf(target, leftover)] : [],
    );
    removeRuffleSaves(host, Object.keys(leftover));
    const synced = saves.find((save) => save.slot === AUTOSAVE_SLOT);
    if (synced) writeRuffleSaves(host, unzipRuffleSaves(synced.bytes));
    saveSync = sync;
  } catch (error) {
    console.error("[Ruffle] Saves are unavailable", error);
  }
}

function pushSaves(): Promise<boolean> {
  const sync = saveSync;
  const target = rom.value;
  if (!sync || !target) return Promise.resolve(true);
  // A push still in flight already covers this one's work.
  pushing ??= captureSaves(sync, target)
    .then(() => sync.push())
    .catch((error: unknown) => {
      console.error("[Ruffle] Saving failed", error);
      return false;
    })
    .finally(() => {
      pushing = null;
    });
  return pushing;
}

// A push in flight may have read storage before the last write landed.
async function flushSaves(): Promise<boolean> {
  await pushing;
  return pushSaves();
}

const savePoll = useIntervalFn(() => void pushSaves(), SAVE_POLL_MS, {
  immediate: false,
});

function mountPlayer(): boolean {
  const ruffle = window.RufflePlayer.newest();
  const container = document.getElementById("r-v2-ruffle-stage");
  if (!ruffle || !container) return false;

  const created = ruffle.createPlayer();
  container.appendChild(created);
  created.load({
    allowFullScreen: true,
    autoplay: "on",
    backgroundColor: backgroundColor.value,
    forceAlign: true,
    forceScale: true,
    letterbox: "on",
    openUrlMode: "confirm",
    publicPath: "/assets/ruffle/",
    url: swfUrl,
  });
  created.style.width = "100%";
  created.style.height = "100%";
  player = created;
  if (saveSync) savePoll.resume();
  return true;
}

// Ruffle writes every SharedObject as its instance goes.
function destroyPlayer() {
  savePoll.pause();
  player?.remove();
  player = null;
}

async function onPlay() {
  const target = rom.value;
  if (!target || gameRunning.value) return;
  gameRunning.value = true;
  swfUrl = getDownloadPath({ rom: target, purpose: "play" });

  await prepareSaves(target);
  if (!alive.value || !gameRunning.value) return;
  await nextTick();

  if (!mountPlayer()) {
    abortPlay();
    return;
  }

  // Start timing the session only once playback is actually under way, so a
  // failed player creation / load records nothing. The session is ingested
  // on unmount, which is what updates last_played / now_playing / status.
  playSession.start(target);

  if (player?.fullscreenEnabled && fullscreenOnPlay.value) {
    player.enterFullscreen();
  }
}

async function leavePlayer(leave: () => void) {
  const target = rom.value;
  if (quitting.value || !target) return;
  quitting.value = true;

  destroyPlayer();
  if (!(await flushSaves())) {
    const discard = await confirm({
      title: t("play.quit-before-save-synced"),
      confirmText: t("common.discard"),
      cancelText: t("common.cancel"),
      tone: "danger",
    });
    if (!discard) {
      // The player is gone, so staying restarts the game on its saves.
      mountPlayer();
      quitting.value = false;
      return;
    }
  }

  if (saveSync) removeRuffleSaves(host, Object.keys(storedSaves()));
  saveSync = null;
  gameRunning.value = false;
  quitting.value = false;
  leave();
}

function onBackgroundColorChange() {
  if (rom.value) {
    localStorage.setItem(
      `player:ruffle:${rom.value.id}:backgroundColor`,
      backgroundColor.value,
    );
  }
}

function onlyQuit() {
  if (!player) {
    window.history.back();
    return;
  }
  void leavePlayer(() => window.history.back());
}

onBeforeRouteLeave((to) => {
  if (!player) return exit.guard(to);
  void leavePlayer(() => exit.leave(to.fullPath));
  return false;
});

useEventListener(window, "pagehide", (event: PageTransitionEvent) => {
  const sync = saveSync;
  const target = rom.value;
  // A page kept for back and forward can return to the running game.
  if (event.persisted || !sync || !target) return;
  const saves = storedSaves();
  if (Object.keys(saves).length > 0) {
    sync.captureOnUnload([saveFileOf(target, saves)]);
  }
});

onMounted(async () => {
  const romResponse = await romApi.getRom({ romId });
  rom.value = romResponse.data;

  if (rom.value) {
    const storedColor = localStorage.getItem(
      `player:ruffle:${rom.value.id}:backgroundColor`,
    );
    if (storedColor) backgroundColor.value = storedColor;
  }

  const script = document.createElement("script");
  script.src = "/assets/ruffle/ruffle.js";
  script.onerror = () => {
    const fallback = document.createElement("script");
    fallback.src = `https://unpkg.com/@ruffle-rs/ruffle@${RUFFLE_VERSION}/ruffle.js`;
    document.body.appendChild(fallback);
  };
  document.body.appendChild(script);
});

onBeforeUnmount(() => {
  // Every exit path (Quit, back links, route change) unmounts the view, so
  // this is the single choke point for recording the session.
  savePoll.pause();
  playSession.flush();
});
</script>

<template>
  <PlayerShell
    :hero-rom="heroRom"
    :title="title"
    :platform-label="platformLabel"
    :rom-id="romId"
    :ready="!!rom"
    :running="gameRunning"
    @play="onPlay"
    @quit="onlyQuit"
  >
    <template #settings>
      <div class="r-v2-ruffle__section-label">
        <RIcon icon="mdi-palette" size="16" />
        <span>{{ t("play.select-background-color") }}</span>
      </div>
      <div class="r-v2-ruffle__color-row">
        <input
          v-model="backgroundColor"
          type="color"
          class="r-v2-ruffle__color-input"
          :aria-label="t('play.select-background-color')"
          :title="t('play.select-background-color')"
          @change="onBackgroundColorChange"
        />
        <code class="r-v2-ruffle__color-code">
          {{ backgroundColor.toUpperCase() }}
        </code>
      </div>

      <RSwitch v-model="fullscreenOnPlay" :label="t('play.full-screen')" />
    </template>

    <template #brand>
      <div class="r-v2-ruffle__brand">
        <span>{{ t("play.powered-by") }}</span>
        <img src="/assets/ruffle/ruffle.svg" alt="Ruffle" />
      </div>
    </template>

    <template #stage>
      <div id="r-v2-ruffle-stage" class="r-v2-ruffle__stage" />
    </template>
  </PlayerShell>
</template>

<style scoped>
.r-v2-ruffle__section-label {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: var(--r-font-size-sm);
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--r-color-fg-secondary);
}

.r-v2-ruffle__color-row {
  display: flex;
  align-items: center;
  gap: 12px;
}
.r-v2-ruffle__color-input {
  appearance: none;
  -webkit-appearance: none;
  border: 1px solid var(--r-color-border-strong);
  border-radius: var(--r-radius-sm);
  width: 48px;
  height: 32px;
  padding: 0;
  background: transparent;
  cursor: pointer;
}
.r-v2-ruffle__color-input::-webkit-color-swatch-wrapper {
  padding: 2px;
}
.r-v2-ruffle__color-input::-webkit-color-swatch {
  border: 0;
  border-radius: 3px;
}
.r-v2-ruffle__color-code {
  font-family: var(--r-font-family-mono, monospace);
  font-size: 13px;
  color: var(--r-color-fg-secondary);
  letter-spacing: 0.04em;
}

.r-v2-ruffle__brand {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  font-size: var(--r-font-size-xs);
  color: var(--r-color-fg-faint);
  font-style: italic;
}
.r-v2-ruffle__brand img {
  height: 22px;
}

.r-v2-ruffle__stage {
  width: 100%;
  height: 100%;
  --splash-screen-background: none;
}
</style>
