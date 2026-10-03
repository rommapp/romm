<script setup lang="ts">
import { RSwitch } from "@v2/lib";
import { useEventListener } from "@vueuse/core";
import {
  computed,
  nextTick,
  onBeforeUnmount,
  onMounted,
  ref,
  shallowRef,
} from "vue";
import { useI18n } from "vue-i18n";
import { onBeforeRouteLeave } from "vue-router";
import romApi from "@/services/api/rom";
import storeAuth from "@/stores/auth";
import type { DetailedRom } from "@/stores/roms";
import PlayerShell from "@/v2/components/Player/PlayerShell.vue";
import { useFullscreenPref } from "@/v2/composables/useFullscreenPref";
import { useIsAlive } from "@/v2/composables/useIsAlive";
import { usePlaySession } from "@/v2/composables/usePlaySession";
import { usePlayerExit } from "@/v2/composables/usePlayerExit";
import { usePlayerFullscreen } from "@/v2/composables/usePlayerFullscreen";
import { usePlayerHero } from "@/v2/composables/usePlayerHero";
import { usePlayingWhile } from "@/v2/composables/useStageActive";
import { useUnloadGuard } from "@/v2/composables/useUnloadGuard";
import { focusFromInput } from "@/v2/utils/autofocus";

const { t } = useI18n();
const exit = usePlayerExit();
const alive = useIsAlive();
const authStore = storeAuth();
const { fullscreenOnPlay } = useFullscreenPref();
const playSession = usePlaySession();

const rom = shallowRef<DetailedRom | null>(null);
const gameRunning = ref(false);
// The game takes the keyboard inside its frame, so app hotkeys stand down.
usePlayingWhile(gameRunning);
const quitting = ref(false);
const frame = ref<HTMLIFrameElement | null>(null);
const { enter: enterFullscreen } = usePlayerFullscreen(frame);
let sessionStarted = false;

const { romId, heroRom, title, platformLabel } = usePlayerHero(rom);

// The player keeps saves in a browser database named after the game, so the
// user id keeps each RomM account's saves apart. The server ignores it.
const playerSrc = computed(
  () => `/assets/easyrpg/index.html?game=${romId}-${authStore.user?.id}`,
);

async function onPlay() {
  const currentRom = rom.value;
  if (!currentRom || authStore.user?.id == null) return;

  gameRunning.value = true;

  await nextTick();
  if (fullscreenOnPlay.value) {
    void enterFullscreen();
  }
}

// Browsers deliver keyboard and gamepad input only to the focused frame.
// Play time starts here, so a player page that never loads records none.
function onFrameLoad() {
  focusFromInput(frame.value);
  if (rom.value && !sessionStarted) {
    sessionStarted = true;
    playSession.start(rom.value);
  }
}

function leavePlayer(destination: string) {
  if (quitting.value) return;
  quitting.value = true;
  playSession.flush();
  exit.leave(destination);
}

function onlyQuit() {
  leavePlayer(`/rom/${romId}`);
}

useUnloadGuard(() => gameRunning.value && !quitting.value);

onMounted(async () => {
  const romResponse = await romApi.getRom({ romId });
  if (!alive.value) return;
  rom.value = romResponse.data;
});

onBeforeRouteLeave((to) => exit.guard(to));

useEventListener(window, "pagehide", () => playSession.flush());

onBeforeUnmount(() => playSession.flush());
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

      <p class="r-v2-easyrpg__save-note">
        {{ t("play.easyrpg-browser-save-warning") }}
      </p>
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
        :src="playerSrc"
        :title="t('play.easyrpg-screen')"
        allow="autoplay; fullscreen; gamepad"
        @load="onFrameLoad"
      />
    </template>
  </PlayerShell>
</template>

<style scoped>
.r-v2-easyrpg__save-note {
  margin: 0;
  color: var(--r-color-fg-muted);
  font-size: var(--r-font-size-sm);
}

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
