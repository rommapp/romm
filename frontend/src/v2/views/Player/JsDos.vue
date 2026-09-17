<script setup lang="ts">
import { RSwitch } from "@v2/lib";
import { useEventListener } from "@vueuse/core";
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
import { useFullscreenFallback } from "@/v2/composables/useFullscreenFallback";
import { useFullscreenPref } from "@/v2/composables/useFullscreenPref";
import {
  hasSharedArrayBuffer,
  isRelaunchMarker,
  useIsolatedLaunch,
} from "@/v2/composables/useIsolatedLaunch";
import { usePlaySession } from "@/v2/composables/usePlaySession";
import { usePlayerExit } from "@/v2/composables/usePlayerExit";
import { usePlayerHero } from "@/v2/composables/usePlayerHero";
import { useSnackbar } from "@/v2/composables/useSnackbar";
import { useUnloadGuard } from "@/v2/composables/useUnloadGuard";
import { loadJsDosRuntime } from "./jsDosRuntime";

const { t } = useI18n();
const authStore = storeAuth();
const playingStore = storePlaying();
const { fullscreenOnPlay } = useFullscreenPref();
useFullscreenFallback();
const playSession = usePlaySession();
const snackbar = useSnackbar();
const confirm = useConfirm();
// A launch isolates the document and boots an emulator into it, and the rest
// of the app cannot live there, so a player that ran hands the tab back a
// fresh document.
let runtimeBound = false;
const exit = usePlayerExit(() => runtimeBound);

const rom = shallowRef<DetailedRom | null>(null);
const gameRunning = ref(false);
const quitting = ref(false);
const stage = ref<HTMLDivElement | null>(null);

let dos: JsDosProps | null = null;

const { romId, heroRom, title, platformLabel } = usePlayerHero(rom);

// The DOSBox-X backend is a threaded build, so it needs SharedArrayBuffer.
const {
  intent: relaunched,
  relaunching,
  relaunch: relaunchIsolated,
} = useIsolatedLaunch<true>("jsdos", romId, isRelaunchMarker);

async function onPlay() {
  const currentRom = rom.value;
  const userId = authStore.user?.id;
  if (!currentRom || userId == null) return;

  if (!hasSharedArrayBuffer()) {
    if (!relaunchIsolated(true)) snackbar.error(t("play.https-required"));
    return;
  }

  // Resolves at once when the mount-time load already landed, and waits for it
  // otherwise, so the emulator payloads always follow the base it served from.
  let assetBase: string;
  try {
    assetBase = await loadJsDosRuntime();
  } catch {
    snackbar.error(t("play.stream-error-generic"));
    return;
  }
  // Preserve narrowing across nextTick().
  const dosFactory = window.Dos;
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
  runtimeBound = true;
  dos = dosFactory(stage.value, {
    url: getDownloadPath({ rom: currentRom }),
    backend: "dosboxX",
    backendLocked: true,
    pathPrefix: `${assetBase}/emulators/`,
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
  exit.leave(destination);
}

function onlyQuit() {
  void leavePlayer(`/rom/${romId}`);
}

useUnloadGuard(() => !!dos && !quitting.value);

onMounted(async () => {
  // The runtime reads nothing from the ROM payload, so let both loads overlap
  // instead of holding the 300 KB bundle behind the API roundtrip. Not on a
  // leg that is about to relaunch, which would throw the bundle away.
  if (hasSharedArrayBuffer()) {
    void loadJsDosRuntime().catch((e: unknown) => console.error(e));
  }

  const romResponse = await romApi.getRom({ romId });
  rom.value = romResponse.data;

  if (relaunched) void onPlay();
});

onBeforeRouteLeave((to) => {
  // With nothing running there is nothing to save first.
  if (!dos) return exit.guard(to);
  void leavePlayer(to.fullPath);
  return false;
});

useEventListener(window, "pagehide", () => playSession.flush());

onBeforeUnmount(teardown);
</script>

<template>
  <PlayerShell
    :hero-rom="heroRom"
    :title="title"
    :platform-label="platformLabel"
    :rom-id="romId"
    :ready="!!rom && !relaunching"
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
