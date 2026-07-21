<script setup lang="ts">
// Ruffle — v2 shell for Flash ROMs. The Ruffle injection (script loader,
// createPlayer, fullscreen) is ported verbatim from
// `src/views/Player/RuffleRS/Base.vue` so playback stays identical; only the
// chrome is v2. No shared state with EJS — Flash has its own config.
import { RBtn, RCard, RIcon, RSwitch } from "@v2/lib";
import {
  computed,
  nextTick,
  onBeforeUnmount,
  onMounted,
  ref,
  watch,
} from "vue";
import { useI18n } from "vue-i18n";
import { useRoute, useRouter } from "vue-router";
import { ROUTES } from "@/plugins/router";
import romApi from "@/services/api/rom";
import storeAuth from "@/stores/auth";
import storePlaying from "@/stores/playing";
import storeRoms, { type DetailedRom, type SimpleRom } from "@/stores/roms";
import type { RuffleSourceAPI } from "@/types/ruffle";
import { getDownloadPath } from "@/utils";
import GameCover from "@/v2/components/shared/GameCover.vue";
import { useBackgroundArt } from "@/v2/composables/useBackgroundArt";
import { useFullscreenPref } from "@/v2/composables/useFullscreenPref";
import storeGalleryRoms from "@/v2/stores/galleryRoms";
import { colorCanvas } from "@/v2/tokens";
import { applyLaunchStatus } from "@/v2/utils/romStatus";

const RUFFLE_VERSION = "0.2.0-nightly.2025.8.14";
const DEFAULT_BACKGROUND_COLOR = colorCanvas.bgDeep;

const { t } = useI18n();
const route = useRoute();
const router = useRouter();
const { fullscreenOnPlay } = useFullscreenPref();
const playingStore = storePlaying();
const auth = storeAuth();

const rom = ref<DetailedRom | null>(null);
const gameRunning = ref(false);
const backgroundColor = ref<string>(DEFAULT_BACKGROUND_COLOR);

// Rom id from the route param (available before `rom` resolves) so the hero
// cover paints its `view-transition-name` immediately and the shared-element
// morph from the gallery / details cover pairs on entry.
const morphRomId = computed(() => {
  const r = route.params.rom;
  return typeof r === "string" ? r : null;
});

// Seed synchronously so the hero cover is in the DOM when the view transition
// captures this view and the morph pairs on entry. From GameDetails the full
// DetailedRom is in `currentRom`; on a direct gallery→play only a SimpleRom
// exists, so seed a cover-only `heroSeed` (`rom` stays null until `onMounted`
// refetches). See EmulatorJS for the same pattern.
const seededRom = storeRoms().currentRom;
if (seededRom && String(seededRom.id) === morphRomId.value) {
  rom.value = seededRom;
}
const heroSeed = ref<SimpleRom | null>(null);
if (!rom.value && morphRomId.value != null) {
  heroSeed.value = storeGalleryRoms().getRomById(Number(morphRomId.value));
}
const heroRom = computed<DetailedRom | SimpleRom | null>(
  () => rom.value ?? heroSeed.value,
);

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

const setBgArt = useBackgroundArt();

// The cover is the shared GameCover (same component as gallery + details +
// EmulatorJS) — it owns style/ratio/placeholder. Flash has no disc /
// cartridge metadata, so it's effectively always 2D box art here.

// Background art keeps the plain 2D cover.
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

const title = computed(
  () => heroRom.value?.name || heroRom.value?.fs_name_no_ext || "",
);

const platformLabel = computed(
  () =>
    heroRom.value?.platform_custom_name ||
    heroRom.value?.platform_display_name ||
    "",
);

function onPlay() {
  gameRunning.value = true;
  // Flash games are keyboard-driven; flag the session so global hotkeys
  // and pad-to-UI translation stay muted while the game owns input.
  playingStore.setPlaying(true);

  nextTick(() => {
    if (!rom.value) return;

    const ruffle = window.RufflePlayer.newest();
    if (!ruffle) return;

    const player = ruffle.createPlayer();
    const container = document.getElementById("r-v2-ruffle-stage");
    container?.appendChild(player);
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

    // Record the launch only once playback is actually under way, so a
    // failed player creation / load doesn't leave the game marked playing.
    if (rom.value.rom_user && auth.scopes.includes("roms.user.write")) {
      applyLaunchStatus(rom.value.rom_user);
      romApi.updateUserRomProps({
        romId: rom.value.id,
        data: rom.value.rom_user,
        updateLastPlayed: true,
      });
    }

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

function backToRom() {
  router.push({ name: ROUTES.ROM, params: { rom: rom.value?.id } });
}
function backToPlatform() {
  router.push({
    name: ROUTES.PLATFORM,
    params: { platform: rom.value?.platform_id },
  });
}

onMounted(async () => {
  const romResponse = await romApi.getRom({
    romId: parseInt(route.params.rom as string),
  });
  rom.value = romResponse.data;

  if (rom.value) {
    document.title = `${rom.value.name} | Play`;
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
  // Hand the keyboard and gamepad back to the UI on any exit path.
  playingStore.setPlaying(false);
});
</script>

<template>
  <section v-if="rom || heroSeed" class="r-v2-ruffle">
    <!-- Pre-game configuration -->
    <div v-if="!gameRunning" class="r-v2-ruffle__config">
      <!-- Cover column -->
      <aside class="r-v2-ruffle__cover">
        <GameCover
          class="r-v2-ruffle__cover-box"
          :rom="heroRom"
          :title="title"
          :identified="heroRom?.is_identified ?? true"
          :morph-id="morphRomId"
          morph-static
          hover-motion
        />
        <h1 class="r-v2-ruffle__title">
          {{ title }}
        </h1>
        <p class="r-v2-ruffle__subtitle">
          {{ platformLabel }}
        </p>
      </aside>

      <!-- Settings panel -->
      <RCard class="r-v2-ruffle__panel" variant="flat">
        <div class="r-v2-ruffle__settings">
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

          <RBtn
            size="large"
            variant="flat"
            color="primary"
            block
            prepend-icon="mdi-play-circle"
            class="r-v2-ruffle__play"
            :loading="!rom"
            :disabled="!rom"
            @click="onPlay"
          >
            {{ t("play.play") }}
          </RBtn>

          <RBtn
            block
            variant="text"
            size="small"
            prepend-icon="mdi-arrow-left"
            @click="backToRom"
          >
            {{ t("play.back-to-game-details") }}
          </RBtn>
          <RBtn
            block
            variant="text"
            size="small"
            prepend-icon="mdi-view-grid-outline"
            @click="backToPlatform"
          >
            {{ t("play.back-to-gallery") }}
          </RBtn>
        </div>
      </RCard>

      <div class="r-v2-ruffle__brand">
        <span>{{ t("play.powered-by") }}</span>
        <img src="/assets/ruffle/ruffle.svg" alt="Ruffle" />
      </div>
    </div>

    <!-- Running state — full bleed minus nav -->
    <div v-else class="r-v2-ruffle__stage-wrap">
      <div id="r-v2-ruffle-stage" class="r-v2-ruffle__stage" />
      <RBtn
        class="r-v2-ruffle__quit"
        variant="translucent"
        prepend-icon="mdi-exit-to-app"
        @click="onlyQuit"
      >
        {{ t("play.quit") }}
      </RBtn>
    </div>
  </section>

  <section v-else class="r-v2-ruffle__loading">
    <div class="r-v2-ruffle__spinner" :aria-label="t('common.loading')" />
  </section>
</template>

<style scoped>
.r-v2-ruffle {
  position: relative;
  min-height: calc(100vh - var(--r-nav-h));
  padding: 24px var(--r-row-pad) 48px;
}

.r-v2-ruffle__config {
  display: grid;
  grid-template-columns: 240px 1fr;
  gap: 24px;
  max-width: 820px;
  margin: 0 auto;
}

.r-v2-ruffle__cover {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  gap: 8px;
}

.r-v2-ruffle__cover-box {
  --r-cover-radius: var(--r-radius-lg);
}
/* 2D box art keeps a drop shadow; alt-art (rare for Flash) floats frame-free. */
.r-v2-ruffle__cover-box:not(.game-cover--alt) {
  box-shadow: 0 18px 36px color-mix(in srgb, black 55%, transparent);
}

.r-v2-ruffle__title {
  margin: 10px 0 0;
  font-size: var(--r-font-size-xl);
  font-weight: var(--r-font-weight-bold);
  line-height: 1.2;
}

.r-v2-ruffle__subtitle {
  margin: 0;
  font-size: var(--r-font-size-sm);
  color: var(--r-color-fg-muted);
}

.r-v2-ruffle__panel {
  background: var(--r-color-bg-elevated) !important;
  border: 1px solid var(--r-color-border) !important;
  border-radius: var(--r-radius-lg) !important;
  backdrop-filter: blur(18px);
  -webkit-backdrop-filter: blur(18px);
  display: flex !important;
  flex-direction: column;
  overflow: hidden;
}

.r-v2-ruffle__settings {
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

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

.r-v2-ruffle__play {
  margin-top: 8px;
}

.r-v2-ruffle__brand {
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
.r-v2-ruffle__brand img {
  height: 22px;
}

/* Running state */
.r-v2-ruffle__stage-wrap {
  position: fixed;
  inset: var(--r-nav-h) 0 0 0;
  background: var(--r-color-canvas-bg);
  z-index: 1;
}
.r-v2-ruffle__stage {
  width: 100%;
  height: 100%;
  --splash-screen-background: none;
}
.r-v2-ruffle__quit {
  position: absolute;
  top: 16px;
  right: 16px;
  z-index: 2;
}

.r-v2-ruffle__loading {
  min-height: calc(100vh - var(--r-nav-h));
  display: grid;
  place-items: center;
}
.r-v2-ruffle__spinner {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  border: 2px solid var(--r-color-surface-hover);
  border-top-color: var(--r-color-brand-primary);
  animation: r-v2-ruffle-spin 0.8s linear infinite;
}
@keyframes r-v2-ruffle-spin {
  to {
    transform: rotate(360deg);
  }
}

html[data-bp~="xs"] .r-v2-ruffle__config {
  grid-template-columns: 1fr;
}
html[data-bp~="xs"] .r-v2-ruffle__cover {
  max-width: 240px;
  margin: 0 auto;
}
</style>
