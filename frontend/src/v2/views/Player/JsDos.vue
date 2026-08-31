<script setup lang="ts">
import { RSwitch } from "@v2/lib";
import { nextTick, onBeforeUnmount, onMounted, ref, shallowRef } from "vue";
import { useI18n } from "vue-i18n";
import { onBeforeRouteLeave } from "vue-router";
import romApi from "@/services/api/rom";
import storeAuth from "@/stores/auth";
import storePlaying from "@/stores/playing";
import type { DetailedRom } from "@/stores/roms";
import type { JsDosProps } from "@/types/js-dos";
import { getDownloadPath } from "@/utils";
import PlayerShell from "@/v2/components/Player/PlayerShell.vue";
import { useConfirm } from "@/v2/composables/useConfirm";
import { useFullscreenPref } from "@/v2/composables/useFullscreenPref";
import { usePlaySession } from "@/v2/composables/usePlaySession";
import { usePlayerHero } from "@/v2/composables/usePlayerHero";
import { useSnackbar } from "@/v2/composables/useSnackbar";
import { isJsResource, loadScript } from "./scriptLoader";

const JSDOS_LOCAL_BASE = "/assets/jsdos";
// Fallback for slim images and the dev server, which ship no local copy. Pinned
// to the image's JSDOS_VERSION; jsDelivr sends the CORP the player's COEP needs.
const JSDOS_CDN_BASE = "https://cdn.jsdelivr.net/npm/js-dos@8.4.1/dist";

// Where the runtime actually came from, so the emulator payloads follow it.
let jsDosAssetBase = JSDOS_LOCAL_BASE;

const { t } = useI18n();
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

const { romId, heroRom, title, platformLabel } = usePlayerHero(rom);

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
    // js-dos calls exitFullscreen() unguarded when this is false, which
    // rejects if the document was never fullscreen. Only ever opt in.
    ...(fullscreenOnPlay.value ? { fullScreen: true } : {}),
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
  <PlayerShell
    :hero-rom="heroRom"
    :title="title"
    :platform-label="platformLabel"
    :rom-id="romId"
    :ready="!!rom"
    :running="gameRunning"
    :quitting="quitting"
    @play="onPlay"
    @quit="onlyQuit"
  >
    <template #settings>
      <RSwitch v-model="fullscreenOnPlay" :label="t('play.full-screen')" />

      <p class="r-v2-jsdos__save-note">
        {{ t("play.jsdos-browser-save-warning") }}
      </p>
    </template>

    <template #stage>
      <div ref="stage" class="r-v2-jsdos__stage" />
    </template>
  </PlayerShell>
</template>

<style scoped>
.r-v2-jsdos__save-note {
  margin: 0;
  color: var(--r-color-fg-muted);
  font-size: var(--r-font-size-sm);
}

.r-v2-jsdos__stage {
  width: 100%;
  height: 100%;
}
</style>
