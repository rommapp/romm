<script setup lang="ts">
import { RBtn, RCard, RSpinner, RSwitch } from "@v2/lib";
import {
  computed,
  nextTick,
  onBeforeUnmount,
  onMounted,
  ref,
  shallowRef,
} from "vue";
import { useI18n } from "vue-i18n";
import { onBeforeRouteLeave, useRoute, useRouter } from "vue-router";
import { ROUTES } from "@/plugins/router";
import romApi from "@/services/api/rom";
import storeAuth from "@/stores/auth";
import storePlaying from "@/stores/playing";
import storeRoms, { type DetailedRom, type SimpleRom } from "@/stores/roms";
import type { JsDosProps } from "@/types/js-dos";
import { getDownloadPath } from "@/utils";
import GameCover from "@/v2/components/shared/GameCover.vue";
import { useBackgroundArt } from "@/v2/composables/useBackgroundArt";
import { useConfirm } from "@/v2/composables/useConfirm";
import { useFullscreenPref } from "@/v2/composables/useFullscreenPref";
import { usePageTitle } from "@/v2/composables/usePageTitle";
import { usePlaySession } from "@/v2/composables/usePlaySession";
import { useSnackbar } from "@/v2/composables/useSnackbar";
import storeGalleryRoms from "@/v2/stores/galleryRoms";
import { isJsResource, loadScript } from "./scriptLoader";

// The full image serves the runtime same-origin. Slim images and the dev
// server ship no local copy, so fall back to jsDelivr: it serves the same
// pinned dist with `cross-origin-resource-policy: cross-origin`, which the
// player's COEP requires. Keep the version in step with docker/Dockerfile.
const JSDOS_LOCAL_BASE = "/assets/jsdos";
const JSDOS_CDN_BASE = "https://cdn.jsdelivr.net/npm/js-dos@8.4.1/dist";

// Where the runtime actually came from, so the emulator payloads follow it.
let jsDosAssetBase = JSDOS_LOCAL_BASE;

const { t } = useI18n();
const route = useRoute();
const router = useRouter();
const authStore = storeAuth();
const playingStore = storePlaying();
const { fullscreenOnPlay } = useFullscreenPref();
const playSession = usePlaySession();
const snackbar = useSnackbar();
const confirm = useConfirm();

const rom = shallowRef<DetailedRom | null>(null);
const gameRunning = ref(false);
const quitting = ref(false);
const stage = ref<HTMLDivElement | null>(null);

let dos: JsDosProps | null = null;

const romId = Number(route.params.rom);

// Seed the cover before the full ROM request resolves so the view transition
// has an element to morph onto.
const seededRom = storeRoms().currentRom;
if (seededRom?.id === romId) {
  rom.value = seededRom;
}
const heroSeed = shallowRef<SimpleRom | null>(null);
if (!rom.value) {
  heroSeed.value = storeGalleryRoms().getRomById(romId);
}
const heroRom = computed<DetailedRom | SimpleRom | null>(
  () => rom.value ?? heroSeed.value,
);

const setBgArt = useBackgroundArt();

const title = computed(
  () => heroRom.value?.name || heroRom.value?.fs_name_no_ext || "",
);

usePageTitle(() =>
  title.value ? t("play.page-title", { name: title.value }) : null,
);

const platformLabel = computed(
  () =>
    heroRom.value?.platform_custom_name ||
    heroRom.value?.platform_display_name ||
    "",
);

async function loadRuntime() {
  jsDosAssetBase = (await isJsResource(`${JSDOS_LOCAL_BASE}/js-dos.js`))
    ? JSDOS_LOCAL_BASE
    : JSDOS_CDN_BASE;

  const css = document.createElement("link");
  css.rel = "stylesheet";
  css.href = `${jsDosAssetBase}/js-dos.css`;
  document.head.appendChild(css);

  await loadScript(`${jsDosAssetBase}/js-dos.js`);
}

async function onPlay() {
  // Preserve narrowing across nextTick().
  const dosFactory = window.Dos;
  const currentRom = rom.value;
  const userId = authStore.user?.id;
  if (!currentRom || userId == null) return;
  if (!dosFactory) {
    snackbar.error(t("play.stream-error-generic"));
    return;
  }
  gameRunning.value = true;
  // Let the emulator own keyboard input while running.
  playingStore.setPlaying(true);

  await nextTick();
  if (!stage.value) {
    gameRunning.value = false;
    playingStore.setPlaying(false);
    return;
  }

  // DOSBox-X provides Windows support.
  dos = dosFactory(stage.value, {
    url: getDownloadPath({ rom: currentRom }),
    backend: "dosboxX",
    backendLocked: true,
    pathPrefix: `${jsDosAssetBase}/emulators/`,
    autoStart: true,
    autoSave: true,
    fullScreen: fullscreenOnPlay.value,
    fsChanges: {
      local: true,
      // js-dos defaults to the bundle URL, which would share saves between
      // RomM accounts using the same browser profile.
      urlToKey: async () => `romm-user-${userId}-rom-${currentRom.id}.changes`,
    },
  });
  // Hide the dos.zone cloud integration.
  dos.setNoCloud(true);

  playSession.start(currentRom);
}

function stopDos() {
  const handle = dos;
  dos = null;
  if (!handle) return;
  void handle.stop().catch((error) => {
    console.error("[js-dos] Stop failed", error);
  });
}

async function saveQuietly(handle: JsDosProps) {
  try {
    return await handle.save();
  } catch (error) {
    console.error("[js-dos] Final save failed", error);
    return false;
  }
}

function teardown() {
  playSession.flush();
  playingStore.setPlaying(false);
  stopDos();
}

async function leavePlayer(destination: string) {
  if (quitting.value) return;
  quitting.value = true;

  const handle = dos;
  if (handle && !(await saveQuietly(handle))) {
    snackbar.error(t("play.stream-save-unconfirmed"));
    const discard = await confirm({
      title: t("play.jsdos-quit-without-saving"),
      confirmText: t("common.discard"),
      cancelText: t("common.cancel"),
      tone: "danger",
    });
    if (!discard) {
      quitting.value = false;
      return;
    }
  }

  teardown();
  window.location.replace(destination);
}

function onlyQuit() {
  void leavePlayer(`/rom/${romId}`);
}
function backToRom() {
  router.push({ name: ROUTES.ROM, params: { rom: romId } });
}
function backToPlatform() {
  const platformId = heroRom.value?.platform_id;
  if (platformId == null) return;
  router.push({
    name: ROUTES.PLATFORM,
    params: { platform: platformId },
  });
}

function onBeforeUnload(event: BeforeUnloadEvent) {
  if (!dos || quitting.value) return;
  event.preventDefault();
  event.returnValue = "";
}

onMounted(async () => {
  window.addEventListener("beforeunload", onBeforeUnload);

  // The runtime reads nothing from the ROM payload, so let both loads overlap
  // instead of holding the 300 KB bundle behind the API roundtrip.
  void loadRuntime().catch((e) => console.error(e));

  const romResponse = await romApi.getRom({ romId });
  rom.value = romResponse.data;

  const { path_cover_large, path_cover_small, url_cover } = romResponse.data;
  const cover = path_cover_large ?? path_cover_small ?? url_cover;
  if (cover) setBgArt(cover);
});

onBeforeRouteLeave((to) => {
  void leavePlayer(to.fullPath);
  return false;
});

onBeforeUnmount(() => {
  window.removeEventListener("beforeunload", onBeforeUnload);
  teardown();
});
</script>

<template>
  <section v-if="rom || heroSeed" class="r-v2-jsdos">
    <div v-if="!gameRunning" class="r-v2-jsdos__config">
      <aside class="r-v2-jsdos__cover">
        <GameCover
          class="r-v2-jsdos__cover-box"
          :rom="heroRom"
          :title="title"
          :identified="heroRom?.is_identified ?? true"
          :morph-id="romId"
          style-context="player"
          morph-static
          hover-motion
        />
        <h1 class="r-v2-jsdos__title">
          {{ title }}
        </h1>
        <p class="r-v2-jsdos__subtitle">
          {{ platformLabel }}
        </p>
      </aside>

      <RCard class="r-v2-jsdos__panel" variant="flat">
        <div class="r-v2-jsdos__settings">
          <RSwitch v-model="fullscreenOnPlay" :label="t('play.full-screen')" />

          <p class="r-v2-jsdos__save-note">
            {{ t("play.jsdos-browser-save-warning") }}
          </p>

          <RBtn
            size="large"
            variant="flat"
            color="primary"
            block
            prepend-icon="mdi-play-circle"
            class="r-v2-jsdos__play"
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
    </div>

    <div v-else class="r-v2-jsdos__stage-wrap">
      <div ref="stage" class="r-v2-jsdos__stage" />
      <RBtn
        class="r-v2-jsdos__quit"
        variant="translucent"
        prepend-icon="mdi-exit-to-app"
        :loading="quitting"
        :disabled="quitting"
        @click="onlyQuit"
      >
        {{ t("play.quit") }}
      </RBtn>
    </div>
  </section>

  <section v-else class="r-v2-jsdos__loading">
    <RSpinner :size="40" :aria-label="t('common.loading')" />
  </section>
</template>

<style scoped>
.r-v2-jsdos {
  position: relative;
  min-height: calc(100vh - var(--r-nav-h));
  padding: 24px var(--r-row-pad) 48px;
}

.r-v2-jsdos__config {
  display: grid;
  grid-template-columns: 240px 1fr;
  gap: 24px;
  max-width: 820px;
  margin: 0 auto;
}

.r-v2-jsdos__cover {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  gap: 8px;
}

.r-v2-jsdos__cover-box {
  --r-cover-radius: var(--r-radius-lg);
}
.r-v2-jsdos__cover-box:not(.game-cover--alt) {
  box-shadow: 0 18px 36px color-mix(in srgb, black 55%, transparent);
}

.r-v2-jsdos__title {
  margin: 10px 0 0;
  font-size: var(--r-font-size-xl);
  font-weight: var(--r-font-weight-bold);
  line-height: 1.2;
}

.r-v2-jsdos__subtitle {
  margin: 0;
  font-size: var(--r-font-size-sm);
  color: var(--r-color-fg-muted);
}

.r-v2-jsdos__panel {
  background: var(--r-color-bg-elevated) !important;
  border: 1px solid var(--r-color-border) !important;
  border-radius: var(--r-radius-lg) !important;
  backdrop-filter: blur(18px);
  display: flex !important;
  flex-direction: column;
  overflow: hidden;
}

.r-v2-jsdos__settings {
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.r-v2-jsdos__play {
  margin-top: 8px;
}

.r-v2-jsdos__save-note {
  margin: 0;
  color: var(--r-color-fg-muted);
  font-size: var(--r-font-size-sm);
}

.r-v2-jsdos__stage-wrap {
  position: fixed;
  inset: var(--r-nav-h) 0 0 0;
  background: var(--r-color-canvas-bg);
  z-index: 1;
}
.r-v2-jsdos__stage {
  width: 100%;
  height: 100%;
}
.r-v2-jsdos__quit {
  position: absolute;
  top: 16px;
  right: 16px;
  z-index: 2;
}

.r-v2-jsdos__loading {
  min-height: calc(100vh - var(--r-nav-h));
  display: grid;
  place-items: center;
}

html[data-bp~="xs"] .r-v2-jsdos__config {
  grid-template-columns: 1fr;
}
html[data-bp~="xs"] .r-v2-jsdos__cover {
  max-width: 240px;
  margin: 0 auto;
}
</style>
