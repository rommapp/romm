<script setup lang="ts">
// Plays PICO-8 carts through the FAKE-08 WebAssembly runtime.
import { RBtn, RSpinner, RSwitch } from "@v2/lib";
import { useEventListener, useFullscreen } from "@vueuse/core";
import { nextTick, onBeforeUnmount, onMounted, ref, shallowRef } from "vue";
import { useI18n } from "vue-i18n";
import romApi from "@/services/api/rom";
import storePlaying from "@/stores/playing";
import type { DetailedRom } from "@/stores/roms";
import { getDownloadPath } from "@/utils";
import PlayerShell from "@/v2/components/Player/PlayerShell.vue";
import { useFullscreenPref } from "@/v2/composables/useFullscreenPref";
import { useInputModality } from "@/v2/composables/useInputModality";
import { useIsAlive } from "@/v2/composables/useIsAlive";
import { usePlaySession } from "@/v2/composables/usePlaySession";
import { usePlayerHero } from "@/v2/composables/usePlayerHero";
import { useSnackbar } from "@/v2/composables/useSnackbar";
import { useUnloadGuard } from "@/v2/composables/useUnloadGuard";
import { createPico8Audio, type Pico8Audio } from "./pico8Audio";
import { createPico8Input } from "./pico8Input";
import { createPico8Pacer, type Pico8Pacer } from "./pico8Pacer";
import {
  createPico8Runtime,
  PICO8_FRAME_RATE,
  PICO8_HEIGHT,
  PICO8_INPUT_BITS,
  PICO8_WIDTH,
  type Pico8Runtime,
} from "./pico8Runtime";

const { t } = useI18n();
const playingStore = storePlaying();
const playSession = usePlaySession();
const snackbar = useSnackbar();
const { fullscreenOnPlay } = useFullscreenPref();
const { modality } = useInputModality();
const alive = useIsAlive();

const rom = shallowRef<DetailedRom | null>(null);
const gameRunning = ref(false);
const loading = ref(false);
const stage = ref<HTMLDivElement | null>(null);
const canvas = ref<HTMLCanvasElement | null>(null);

const { romId, heroRom, title, platformLabel } = usePlayerHero(rom);
const {
  isFullscreen,
  enter: enterFullscreen,
  toggle: toggleFullscreen,
} = useFullscreen(stage);

let runtime: Pico8Runtime | null = null;
let audio: Pico8Audio | null = null;
let pacer: Pico8Pacer | null = null;
let animationFrame = 0;

const input = createPico8Input();
const { touchMask } = input;

const directionControls = [
  {
    bit: PICO8_INPUT_BITS.up,
    icon: "mdi-menu-up",
    label: "up",
    labelKey: "play.pico8-up",
  },
  {
    bit: PICO8_INPUT_BITS.left,
    icon: "mdi-menu-left",
    label: "left",
    labelKey: "play.pico8-left",
  },
  {
    bit: PICO8_INPUT_BITS.right,
    icon: "mdi-menu-right",
    label: "right",
    labelKey: "play.pico8-right",
  },
  {
    bit: PICO8_INPUT_BITS.down,
    icon: "mdi-menu-down",
    label: "down",
    labelKey: "play.pico8-down",
  },
] as const;

const faceControls = [
  { bit: PICO8_INPUT_BITS.a, color: "danger", label: "A" },
  { bit: PICO8_INPUT_BITS.b, color: "primary", label: "B" },
] as const;

useUnloadGuard(gameRunning);

function focusPlayButton() {
  document.querySelector<HTMLElement>(".r-v2-player__play")?.focus({
    preventScroll: true,
  });
}

function onKeyDown(event: KeyboardEvent) {
  if (!gameRunning.value) return;
  if (input.pressKey(event.code)) event.preventDefault();
}

function onKeyUp(event: KeyboardEvent) {
  input.releaseKey(event.code);
}

function trackMouse(event: PointerEvent) {
  const element = canvas.value;
  if (!element) return;
  const rect = element.getBoundingClientRect();
  input.moveMouse(
    event.clientX - rect.left,
    event.clientY - rect.top,
    rect.width,
    rect.height,
  );
}

function onCanvasPointerMove(event: PointerEvent) {
  if (!gameRunning.value) return;
  trackMouse(event);
}

function onCanvasPointerDown(event: PointerEvent) {
  if (!gameRunning.value) return;
  event.preventDefault();
  trackMouse(event);
  input.pressMouse(event.button);
  canvas.value?.setPointerCapture(event.pointerId);
}

function onCanvasPointerUp(event: PointerEvent) {
  trackMouse(event);
  input.releaseMouse(event.button);
}

function onControlPointerDown(bit: number, event: PointerEvent) {
  if (!gameRunning.value) return;
  event.preventDefault();
  input.pressTouch(bit);
  (event.currentTarget as HTMLElement).setPointerCapture?.(event.pointerId);
}

function onControlPointerUp(bit: number, event: PointerEvent) {
  event.preventDefault();
  input.releaseTouch(bit);
}

function onControlKeyDown(bit: number, event: KeyboardEvent) {
  if (!gameRunning.value || !["Enter", "Space"].includes(event.code)) return;
  event.preventDefault();
  input.pressTouch(bit);
}

function onControlKeyUp(bit: number) {
  input.releaseTouch(bit);
}

function runFrame(timestamp: number) {
  const active = runtime;
  if (!gameRunning.value || !active || !pacer) return;

  try {
    const steps = pacer.tick(timestamp);
    for (let step = 0; step < steps; step += 1) {
      active.advance(input.read());
      audio?.pump((target) => active.readAudio(target));
    }
    // Several emulated frames may land in one tick, but only the last is seen.
    if (steps > 0) active.render();
  } catch (error) {
    showPlayError(error);
    return;
  }
  animationFrame = requestAnimationFrame(runFrame);
}

function startLoop() {
  pacer = createPico8Pacer(runtime?.frameRate || PICO8_FRAME_RATE);
  pacer.reset(performance.now());
  animationFrame = requestAnimationFrame(runFrame);
}

function releaseGame() {
  cancelAnimationFrame(animationFrame);
  animationFrame = 0;
  runtime?.dispose();
  runtime = null;
  pacer = null;
  audio?.close();
  audio = null;
  input.reset();
  playSession.flush();
  playingStore.setPlaying(false);
  gameRunning.value = false;
  loading.value = false;
}

function showPlayError(error: unknown) {
  console.error("[PICO-8] Playback failed", error);
  snackbar.error(t("play.stream-error-generic"));
  releaseGame();
}

async function fetchCartBytes(target: DetailedRom) {
  const response = await fetch(getDownloadPath({ rom: target }));
  if (!response.ok) throw new Error(`ROM request failed: ${response.status}`);
  return new Uint8Array(await response.arrayBuffer());
}

async function onPlay() {
  const currentRom = rom.value;
  if (!currentRom || gameRunning.value) return;

  gameRunning.value = true;
  loading.value = true;
  playingStore.setPlaying(true);
  await nextTick();

  if (!gameRunning.value) return;
  const canvasElement = canvas.value;
  if (!canvasElement) {
    showPlayError(new Error("PICO-8 canvas is unavailable"));
    return;
  }

  let nextRuntime: Pico8Runtime | null = null;
  try {
    const [runtimeResult, bytes] = await Promise.all([
      createPico8Runtime(canvasElement),
      fetchCartBytes(currentRom),
    ]);
    nextRuntime = runtimeResult;
    if (!gameRunning.value) {
      nextRuntime.dispose();
      nextRuntime = null;
      return;
    }
    nextRuntime.loadCart(bytes);
    runtime = nextRuntime;
    nextRuntime = null;

    // A cart is playable without sound, so a failed audio graph only warns.
    try {
      audio = await createPico8Audio({
        sampleRate: runtime.audioSampleRate,
        samplesPerFrame: runtime.samplesPerFrame,
      });
    } catch (error) {
      console.warn("[PICO-8] Audio is unavailable", error);
      audio = null;
    }
    if (!gameRunning.value) {
      releaseGame();
      return;
    }

    loading.value = false;
    playSession.start(currentRom);
    if (fullscreenOnPlay.value) void enterFullscreen().catch(() => {});
    startLoop();
  } catch (error) {
    nextRuntime?.dispose();
    if (!gameRunning.value) return;
    showPlayError(error);
  }
}

function onlyQuit() {
  releaseGame();
  window.history.back();
}

useEventListener(window, "keydown", onKeyDown);
useEventListener(window, "keyup", onKeyUp);
useEventListener(window, "blur", input.reset);

onMounted(async () => {
  const romResponse = await romApi.getRom({ romId });
  if (!alive.value) return;
  rom.value = romResponse.data;
  if (modality.value === "pad" || modality.value === "key") {
    await nextTick();
    if (!alive.value) return;
    focusPlayButton();
  }
});

onBeforeUnmount(releaseGame);
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
  >
    <template #stage-actions>
      <div class="r-v2-pico8__actions">
        <RBtn
          variant="translucent"
          :icon="isFullscreen ? 'mdi-fullscreen-exit' : 'mdi-fullscreen'"
          :aria-label="
            isFullscreen ? t('play.exit-full-screen') : t('play.full-screen')
          "
          :title="
            isFullscreen ? t('play.exit-full-screen') : t('play.full-screen')
          "
          @click="toggleFullscreen"
        />
        <RBtn
          variant="translucent"
          icon="mdi-exit-to-app"
          :aria-label="t('play.quit')"
          :title="t('play.quit')"
          @click="onlyQuit"
        />
      </div>
    </template>

    <template #settings>
      <RSwitch v-model="fullscreenOnPlay" :label="t('play.full-screen')" />
    </template>

    <template #brand>
      <div class="r-v2-pico8__brand">
        <span>{{ t("play.powered-by") }}</span>
        <strong>PICO-8</strong>
      </div>
    </template>

    <template #stage>
      <div ref="stage" class="r-v2-pico8__stage">
        <div class="r-v2-pico8__viewport">
          <div class="r-v2-pico8__screen">
            <canvas
              ref="canvas"
              class="r-v2-pico8__canvas"
              :width="PICO8_WIDTH"
              :height="PICO8_HEIGHT"
              :aria-label="t('play.pico8-screen')"
              @pointermove="onCanvasPointerMove"
              @pointerdown="onCanvasPointerDown"
              @pointerup="onCanvasPointerUp"
              @pointercancel="input.clearMouse"
              @lostpointercapture="input.clearMouse"
              @contextmenu.prevent
            />
            <div v-if="loading" class="r-v2-pico8__loading">
              <RSpinner :size="32" :aria-label="t('common.loading')" />
            </div>
          </div>
        </div>

        <div
          class="r-v2-pico8__controls"
          role="group"
          :aria-label="t('play.pico8-controls')"
        >
          <div class="r-v2-pico8__dpad">
            <RBtn
              v-for="control in directionControls"
              :key="control.label"
              :icon="control.icon"
              variant="translucent"
              size="small"
              :class="[
                'r-v2-pico8__control',
                `r-v2-pico8__control--${control.label}`,
                {
                  'r-v2-pico8__control--held': touchMask & control.bit,
                },
              ]"
              :aria-label="t(control.labelKey)"
              :title="t(control.labelKey)"
              @pointerdown.stop.prevent="
                onControlPointerDown(control.bit, $event)
              "
              @pointerup.stop="onControlPointerUp(control.bit, $event)"
              @pointercancel.stop="onControlPointerUp(control.bit, $event)"
              @lostpointercapture="onControlPointerUp(control.bit, $event)"
              @keydown.stop="onControlKeyDown(control.bit, $event)"
              @keyup.stop="onControlKeyUp(control.bit)"
              @blur.stop="onControlKeyUp(control.bit)"
            />
          </div>

          <div class="r-v2-pico8__face-buttons">
            <RBtn
              v-for="control in faceControls"
              :key="control.label"
              size="large"
              :color="control.color"
              variant="translucent"
              class="r-v2-pico8__control"
              :class="{
                'r-v2-pico8__control--held': touchMask & control.bit,
              }"
              :aria-label="control.label"
              :title="control.label"
              @pointerdown.stop.prevent="
                onControlPointerDown(control.bit, $event)
              "
              @pointerup.stop="onControlPointerUp(control.bit, $event)"
              @pointercancel.stop="onControlPointerUp(control.bit, $event)"
              @lostpointercapture="onControlPointerUp(control.bit, $event)"
              @keydown.stop="onControlKeyDown(control.bit, $event)"
              @keyup.stop="onControlKeyUp(control.bit)"
              @blur.stop="onControlKeyUp(control.bit)"
            >
              {{ control.label }}
            </RBtn>
          </div>
        </div>
      </div>
    </template>
  </PlayerShell>
</template>

<style scoped>
.r-v2-pico8__stage {
  --r-pico8-stage-pad: 24px;
  width: 100%;
  height: 100%;
  display: grid;
  grid-template-rows: minmax(0, 1fr) auto;
  justify-items: center;
  align-items: center;
  gap: 20px;
  overflow: hidden;
  padding: var(--r-pico8-stage-pad);
  box-sizing: border-box;
}

/* The bottom tab bar overlays the stage on sm-and-down, so keep the on-screen
   controls clear of it. */
html[data-bp~="sm-and-down"] .r-v2-pico8__stage {
  padding-bottom: calc(
    var(--r-pico8-stage-pad) + var(--r-bottom-nav-h) +
      env(safe-area-inset-bottom)
  );
}

.r-v2-pico8__stage:fullscreen {
  background: var(--r-color-canvas-bg);
}

.r-v2-pico8__viewport {
  width: 100%;
  height: 100%;
  min-width: 0;
  min-height: 0;
  container-type: size;
  display: grid;
  place-items: center;
}

/* The largest square the viewport can hold, so it never outgrows either axis. */
.r-v2-pico8__screen {
  position: relative;
  width: min(100cqw, 100cqh, 640px);
  aspect-ratio: 1;
  background: var(--r-color-canvas-bg);
  box-shadow: 0 18px 48px color-mix(in srgb, black 55%, transparent);
}

.r-v2-pico8__canvas {
  display: block;
  width: 100%;
  height: 100%;
  image-rendering: pixelated;
  image-rendering: crisp-edges;
  touch-action: none;
}

.r-v2-pico8__actions {
  position: absolute;
  right: 16px;
  bottom: 16px;
  z-index: 2;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

/* Clear the bottom tab bar, which overlays this corner on sm-and-down. */
html[data-bp~="sm-and-down"] .r-v2-pico8__actions {
  bottom: calc(16px + var(--r-bottom-nav-h) + env(safe-area-inset-bottom));
}

.r-v2-pico8__loading {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  background: color-mix(in srgb, black 45%, transparent);
}

.r-v2-pico8__controls {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 32px;
  touch-action: none;
  user-select: none;
}

.r-v2-pico8__dpad {
  display: grid;
  grid-template-columns: repeat(3, 42px);
  grid-template-rows: repeat(3, 42px);
  align-items: center;
  justify-items: center;
}

.r-v2-pico8__control {
  min-width: 42px;
  touch-action: none;
  user-select: none;
}

.r-v2-pico8__control--up {
  grid-column: 2;
  grid-row: 1;
}

.r-v2-pico8__control--left {
  grid-column: 1;
  grid-row: 2;
}

.r-v2-pico8__control--right {
  grid-column: 3;
  grid-row: 2;
}

.r-v2-pico8__control--down {
  grid-column: 2;
  grid-row: 3;
}

.r-v2-pico8__control--held {
  filter: brightness(1.35);
}

.r-v2-pico8__face-buttons {
  display: flex;
  align-items: center;
  gap: 12px;
}

.r-v2-pico8__brand {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  color: var(--r-color-fg-faint);
  font-size: var(--r-font-size-xs);
  font-style: italic;
}

.r-v2-pico8__brand strong {
  color: var(--r-color-fg-muted);
  font-style: normal;
}

html[data-bp~="xs"] .r-v2-pico8__stage {
  --r-pico8-stage-pad: 16px;
  gap: 12px;
}

html[data-bp~="xs"] .r-v2-pico8__screen {
  width: min(100cqw, 100cqh, 420px);
}

html[data-bp~="xs"] .r-v2-pico8__controls {
  gap: 16px;
  transform: scale(0.9);
}
</style>
