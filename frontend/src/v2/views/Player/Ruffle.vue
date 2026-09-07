<script setup lang="ts">
// Ruffle — v2 shell for Flash ROMs. The Ruffle injection (script loader,
// createPlayer, fullscreen) is ported verbatim from
// `src/views/Player/RuffleRS/Base.vue` so playback stays identical; only the
// chrome is v2. No shared state with EJS — Flash has its own config.
import { RIcon, RSwitch } from "@v2/lib";
import { nextTick, onBeforeUnmount, onMounted, ref, shallowRef } from "vue";
import { useI18n } from "vue-i18n";
import romApi from "@/services/api/rom";
import storePlaying from "@/stores/playing";
import type { DetailedRom } from "@/stores/roms";
import type { RuffleSourceAPI } from "@/types/ruffle";
import { getDownloadPath } from "@/utils";
import PlayerShell from "@/v2/components/Player/PlayerShell.vue";
import { useFullscreenPref } from "@/v2/composables/useFullscreenPref";
import { usePlaySession } from "@/v2/composables/usePlaySession";
import { usePlayerHero } from "@/v2/composables/usePlayerHero";
import { useUnloadGuard } from "@/v2/composables/useUnloadGuard";
import { colorCanvas } from "@/v2/tokens";

const RUFFLE_VERSION = "0.2.0-nightly.2025.8.14";
const DEFAULT_BACKGROUND_COLOR = colorCanvas.bgDeep;

const { t } = useI18n();
const { fullscreenOnPlay } = useFullscreenPref();
const playingStore = storePlaying();
const playSession = usePlaySession();

const rom = shallowRef<DetailedRom | null>(null);
const gameRunning = ref(false);
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

// Nothing is running, so drop the guard and the input mute the launch armed.
function abortPlay() {
  gameRunning.value = false;
  playingStore.setPlaying(false);
}

function onPlay() {
  gameRunning.value = true;
  // Flash games are keyboard-driven; flag the session so global hotkeys
  // and pad-to-UI translation stay muted while the game owns input.
  playingStore.setPlaying(true);

  nextTick(() => {
    if (!rom.value) {
      abortPlay();
      return;
    }

    const ruffle = window.RufflePlayer.newest();
    if (!ruffle) {
      abortPlay();
      return;
    }

    const player = ruffle.createPlayer();
    const container = document.getElementById("r-v2-ruffle-stage");
    if (!container) {
      abortPlay();
      return;
    }
    container.appendChild(player);
    player.load({
      allowFullScreen: true,
      autoplay: "on",
      backgroundColor: backgroundColor.value,
      forceAlign: true,
      forceScale: true,
      letterbox: "on",
      openUrlMode: "confirm",
      publicPath: "/assets/ruffle/",
      url: getDownloadPath({ rom: rom.value }),
    });
    player.style.width = "100%";
    player.style.height = "100%";

    // Start timing the session only once playback is actually under way, so a
    // failed player creation / load records nothing. The session is ingested
    // on unmount, which is what updates last_played / now_playing / status.
    playSession.start(rom.value);

    if (player.fullscreenEnabled && fullscreenOnPlay.value) {
      player.enterFullscreen();
    }
  });
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
  window.history.back();
}

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
  playSession.flush();
  // Hand the keyboard and gamepad back to the UI on any exit path.
  playingStore.setPlaying(false);
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
