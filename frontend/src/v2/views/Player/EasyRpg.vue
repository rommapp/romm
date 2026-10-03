<script setup lang="ts">
import { RSwitch } from "@v2/lib";
import { useEventListener, useIntervalFn } from "@vueuse/core";
import { nextTick, onBeforeUnmount, onMounted, ref, shallowRef } from "vue";
import { useI18n } from "vue-i18n";
import { onBeforeRouteLeave } from "vue-router";
import romApi from "@/services/api/rom";
import storeAuth from "@/stores/auth";
import type { DetailedRom } from "@/stores/roms";
import PlayerShell from "@/v2/components/Player/PlayerShell.vue";
import { useConfirm } from "@/v2/composables/useConfirm";
import { useFullscreenFallback } from "@/v2/composables/useFullscreenFallback";
import { useFullscreenPref } from "@/v2/composables/useFullscreenPref";
import { useIsAlive } from "@/v2/composables/useIsAlive";
import { usePlaySession } from "@/v2/composables/usePlaySession";
import { usePlayerExit } from "@/v2/composables/usePlayerExit";
import { usePlayerHero } from "@/v2/composables/usePlayerHero";
import { useSnackbar } from "@/v2/composables/useSnackbar";
import { usePlayingWhile } from "@/v2/composables/useStageActive";
import { useUnloadGuard } from "@/v2/composables/useUnloadGuard";
import { focusFromInput } from "@/v2/utils/autofocus";
import { EasyRpgSaveSync } from "@/v2/utils/easyRpgSaves";

// The player writes a save to browser storage as soon as the game saves.
const SAVE_POLL_MS = 5000;

const { t } = useI18n();
const exit = usePlayerExit();
const alive = useIsAlive();
const authStore = storeAuth();
const { fullscreenOnPlay } = useFullscreenPref();
useFullscreenFallback();
const playSession = usePlaySession();
const snackbar = useSnackbar();
const confirm = useConfirm();

const rom = shallowRef<DetailedRom | null>(null);
// The seeded rom can carry stale saves, and the launch plan trusts them.
const romFetched = ref(false);
const gameRunning = ref(false);
// The game takes the keyboard inside its frame, so app hotkeys stand down.
usePlayingWhile(gameRunning);
const preparing = ref(false);
const quitting = ref(false);
const frame = ref<HTMLIFrameElement | null>(null);

let saveSync: EasyRpgSaveSync | null = null;
let pushing: Promise<boolean> | null = null;

const { romId, heroRom, title, platformLabel } = usePlayerHero(rom);

function pushSaves(): Promise<boolean> {
  const sync = saveSync;
  if (!sync) return Promise.resolve(true);
  // A push still in flight already covers this one's work.
  pushing ??= sync
    .push()
    .catch((error: unknown) => {
      console.error("[EasyRPG] Save upload failed", error);
      return false;
    })
    .finally(() => {
      pushing = null;
    });
  return pushing;
}

// A push in flight may have read the saves before the latest one landed.
async function flushSaves(): Promise<boolean> {
  await pushing;
  return pushSaves();
}

const savePoll = useIntervalFn(() => void pushSaves(), SAVE_POLL_MS, {
  immediate: false,
});

async function onPlay() {
  const currentRom = rom.value;
  const userId = authStore.user?.id;
  if (!currentRom || userId == null || preparing.value) return;

  preparing.value = true;
  const sync = new EasyRpgSaveSync(currentRom, String(currentRom.id));
  try {
    await sync.prepare(userId);
  } catch (error) {
    console.error("[EasyRPG] Save download failed", error);
    snackbar.error(t("play.easyrpg-saves-load-failed"));
    return;
  } finally {
    preparing.value = false;
  }
  if (!alive.value) return;

  saveSync = sync;
  gameRunning.value = true;
  savePoll.resume();
  playSession.start(currentRom);

  await nextTick();
  if (fullscreenOnPlay.value) {
    void frame.value?.requestFullscreen().catch(() => undefined);
  }
}

// Browsers deliver keyboard and gamepad input only to the focused frame.
function onFrameLoad() {
  focusFromInput(frame.value);
}

function teardown() {
  savePoll.pause();
  playSession.flush();
  saveSync = null;
}

async function leavePlayer(destination: string) {
  if (quitting.value) return;
  quitting.value = true;

  if (saveSync && !(await flushSaves())) {
    const discard = await confirm({
      title: t("play.easyrpg-quit-without-saving"),
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

useUnloadGuard(() => gameRunning.value && !quitting.value);

onMounted(async () => {
  const romResponse = await romApi.getRom({ romId });
  if (!alive.value) return;
  rom.value = romResponse.data;
  romFetched.value = true;
});

onBeforeRouteLeave((to) => {
  if (!saveSync) return exit.guard(to);
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
    :ready="romFetched && !preparing"
    :running="gameRunning"
    :quitting="quitting"
    @play="onPlay"
    @quit="onlyQuit"
  >
    <template #settings>
      <RSwitch v-model="fullscreenOnPlay" :label="t('play.full-screen')" />
    </template>

    <template #brand>
      <div class="r-v2-easyrpg__brand">
        <span>{{ t("play.powered-by") }}</span>
        <span class="r-v2-easyrpg__brand-name">EasyRPG</span>
      </div>
    </template>

    <template #stage>
      <iframe
        v-if="gameRunning"
        ref="frame"
        class="r-v2-easyrpg__stage"
        :src="`/assets/easyrpg/index.html?game=${romId}`"
        :title="t('play.easyrpg-screen')"
        allow="autoplay; fullscreen; gamepad"
        @load="onFrameLoad"
      />
    </template>
  </PlayerShell>
</template>

<style scoped>
.r-v2-easyrpg__brand {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  font-size: var(--r-font-size-xs);
  color: var(--r-color-fg-faint);
  font-style: italic;
}
.r-v2-easyrpg__brand-name {
  font-style: normal;
  font-weight: 600;
  color: var(--r-color-fg-secondary);
}

.r-v2-easyrpg__stage {
  display: block;
  width: 100%;
  height: 100%;
  border: 0;
}
</style>
