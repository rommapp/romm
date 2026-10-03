<script setup lang="ts">
import { RSwitch } from "@v2/lib";
import { useEventListener } from "@vueuse/core";
import { nextTick, onBeforeUnmount, onMounted, ref, shallowRef } from "vue";
import { useI18n } from "vue-i18n";
import { onBeforeRouteLeave } from "vue-router";
import romApi from "@/services/api/rom";
import { AUTOSAVE_SLOT } from "@/services/api/save";
import storeAuth from "@/stores/auth";
import type { DetailedRom } from "@/stores/roms";
import type { JsDosProps } from "@/types/js-dos";
import { getDownloadPath } from "@/utils";
import PlayerShell from "@/v2/components/Player/PlayerShell.vue";
import { useConfirm } from "@/v2/composables/useConfirm";
import { useFullscreenFallback } from "@/v2/composables/useFullscreenFallback";
import { useFullscreenPref } from "@/v2/composables/useFullscreenPref";
import { useIsAlive } from "@/v2/composables/useIsAlive";
import {
  hasSharedArrayBuffer,
  isRelaunchMarker,
  useIsolatedLaunch,
} from "@/v2/composables/useIsolatedLaunch";
import { usePlaySession } from "@/v2/composables/usePlaySession";
import { usePlayerExit } from "@/v2/composables/usePlayerExit";
import { usePlayerHero } from "@/v2/composables/usePlayerHero";
import { useSnackbar } from "@/v2/composables/useSnackbar";
import { usePlayingWhile } from "@/v2/composables/useStageActive";
import { useUnloadGuard } from "@/v2/composables/useUnloadGuard";
import { DeviceSaveSync, type PlayerSaveFile } from "@/v2/utils/saveSync";
import { loadJsDosRuntime } from "./jsDosRuntime";

const { t } = useI18n();
const authStore = storeAuth();
const { fullscreenOnPlay } = useFullscreenPref();
useFullscreenFallback();
const playSession = usePlaySession();
const snackbar = useSnackbar();
const confirm = useConfirm();
const alive = useIsAlive();
// An isolated document cannot host the rest of the app, so a player that ran
// hands the tab back a fresh one.
let runtimeBound = false;
const exit = usePlayerExit(() => runtimeBound);

const rom = shallowRef<DetailedRom | null>(null);
const gameRunning = ref(false);
usePlayingWhile(gameRunning);
const quitting = ref(false);
const preparing = ref(false);
const stage = ref<HTMLDivElement | null>(null);

let dos: JsDosProps | null = null;
let saveSync: DeviceSaveSync | null = null;

const { romId, heroRom, title, platformLabel } = usePlayerHero(rom);

// The DOSBox-X backend is a threaded build, so it needs SharedArrayBuffer.
const {
  intent: relaunched,
  relaunching,
  relaunch: relaunchIsolated,
} = useIsolatedLaunch<true>("jsdos", romId, isRelaunchMarker);

// The browser storage js-dos kept saves in before they synced; js-dos itself
// would share them between accounts, hence the user in the key.
function legacyChangesKey(userId: number, id: number): string {
  return `romm-user-${userId}-rom-${id}.changes`;
}

async function legacyChangesDir(): Promise<FileSystemDirectoryHandle> {
  const root = await navigator.storage.getDirectory();
  const jsdos = await root.getDirectoryHandle("jsdos");
  return jsdos.getDirectoryHandle("saves");
}

async function readLegacyChanges(
  key: string,
  fileName: string,
): Promise<PlayerSaveFile[]> {
  try {
    const handle = await (await legacyChangesDir()).getFileHandle(key);
    const file = await handle.getFile();
    return [
      {
        slot: AUTOSAVE_SLOT,
        fileName,
        bytes: new Uint8Array(await file.arrayBuffer()),
        updatedAt: file.lastModified,
      },
    ];
  } catch {
    return [];
  }
}

// Once carried into the synced copy it would only overwrite newer progress.
async function forgetLegacyChanges(key: string) {
  try {
    await (await legacyChangesDir()).removeEntry(key);
  } catch {
    // Nothing was kept there.
  }
}

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

  const key = legacyChangesKey(userId, currentRom.id);
  const fileName = `${currentRom.fs_name_no_ext}.changes`;
  const sync = new DeviceSaveSync(currentRom, userId, "jsdos");
  let changes: Uint8Array | null;
  preparing.value = true;
  try {
    const legacy = await readLegacyChanges(key, fileName);
    const saves = await sync.prepare(legacy);
    if (legacy.length) await forgetLegacyChanges(key);
    changes = saves.find((save) => save.slot === AUTOSAVE_SLOT)?.bytes ?? null;
  } catch (error) {
    console.error("[js-dos] Save storage failed", error);
    snackbar.error(t("play.stream-error-generic"));
    return;
  } finally {
    preparing.value = false;
  }
  if (!alive.value) return;

  saveSync = sync;
  gameRunning.value = true;

  await nextTick();
  if (!stage.value) {
    gameRunning.value = false;
    return;
  }

  // DOSBox-X provides Windows support.
  runtimeBound = true;
  dos = dosFactory(stage.value, {
    url: getDownloadPath({ rom: currentRom, purpose: "play" }),
    backend: "dosboxX",
    backendLocked: true,
    pathPrefix: `${assetBase}/emulators/`,
    autoStart: true,
    autoSave: true,
    // js-dos calls exitFullscreen() unguarded when this is false, which
    // rejects if the document was never fullscreen. Only ever opt in.
    ...(fullscreenOnPlay.value ? { fullScreen: true } : {}),
    // The changes live in RomM's synced copy, never in js-dos's own storage.
    fsChanges: {
      local: false,
      urlToKey: async () => key,
      pull: async () => changes,
      push: async (_key, bytes) => {
        changes = bytes;
        await sync.capture([
          { slot: AUTOSAVE_SLOT, fileName, bytes, updatedAt: Date.now() },
        ]);
        if (!(await sync.push())) throw new Error("Save upload failed");
      },
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
  stopDos();
  saveSync = null;
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
  // The runtime reads nothing from the ROM payload, so overlap the two loads.
  // Not on a leg about to relaunch, which would throw the bundle away.
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

useEventListener(window, "pagehide", () => {
  saveSync?.pushOnUnload();
  playSession.flush();
});

onBeforeUnmount(teardown);
</script>

<template>
  <PlayerShell
    :hero-rom="heroRom"
    :title="title"
    :platform-label="platformLabel"
    :rom-id="romId"
    :ready="!!rom && !relaunching && !preparing"
    :running="gameRunning"
    :quitting="quitting"
    @play="onPlay"
    @quit="onlyQuit"
  >
    <template #settings>
      <RSwitch v-model="fullscreenOnPlay" :label="t('play.full-screen')" />
    </template>

    <template #stage>
      <div ref="stage" class="r-v2-jsdos__stage" />
    </template>
  </PlayerShell>
</template>

<style scoped>
.r-v2-jsdos__stage {
  width: 100%;
  height: 100%;
}
</style>
