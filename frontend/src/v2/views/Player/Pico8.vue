<script setup lang="ts">
// Plays PICO-8 carts through the FAKE-08 WebAssembly runtime served from
// /assets/pico8 (provisioned by the emulator stage of docker/Dockerfile).
import { RBtn, RSpinner, RSwitch } from "@v2/lib";
import { useEventListener } from "@vueuse/core";
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
const touchMask = ref(0);

const { romId, heroRom, title, platformLabel } = usePlayerHero(rom);

let runtime: Pico8Runtime | null = null;
let animationFrame = 0;
let lastFrameTime = 0;
let frameAccumulator = 0;
let previousHeld = 0;
let keyboardMask = 0;
let mouseX = 0;
let mouseY = 0;
let mouseButtons = 0;
let audioContext: AudioContext | null = null;
let audioGain: GainNode | null = null;
let nextAudioTime = 0;
let frameDuration = 1000 / PICO8_FRAME_RATE;

const input = { keyDown: 0, keyHeld: 0, mouseX: 0, mouseY: 0, mouseButtons: 0 };

const keyboardMap: Record<string, number> = {
  ArrowLeft: PICO8_INPUT_BITS.left,
  ArrowRight: PICO8_INPUT_BITS.right,
  ArrowUp: PICO8_INPUT_BITS.up,
  ArrowDown: PICO8_INPUT_BITS.down,
  KeyZ: PICO8_INPUT_BITS.a,
  KeyX: PICO8_INPUT_BITS.b,
};

// W3C standard-mapping button index to PICO-8 bit.
const padButtonBits = [
  [0, PICO8_INPUT_BITS.a],
  [1, PICO8_INPUT_BITS.b],
  [12, PICO8_INPUT_BITS.up],
  [13, PICO8_INPUT_BITS.down],
  [14, PICO8_INPUT_BITS.left],
  [15, PICO8_INPUT_BITS.right],
] as const;

// Per stick axis, the bit for a negative then a positive deflection.
const padAxisBits = [
  [PICO8_INPUT_BITS.left, PICO8_INPUT_BITS.right],
  [PICO8_INPUT_BITS.up, PICO8_INPUT_BITS.down],
] as const;
const PAD_AXIS_THRESHOLD = 0.5;

// Pointer button number to the mask FAKE-08 expects (left, middle, right).
const mouseButtonBits = [0x01, 0x04, 0x02];

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
  const bit = keyboardMap[event.code];
  if (!bit) return;
  event.preventDefault();
  keyboardMask |= bit;
}

function onKeyUp(event: KeyboardEvent) {
  const bit = keyboardMap[event.code];
  if (bit) keyboardMask &= ~bit;
}

function readGamepadMask() {
  let mask = 0;
  for (const gamepad of navigator.getGamepads?.() ?? []) {
    // Firefox keeps disconnected entries, whose stale analog values drift
    // across the threshold and press buttons on their own. #3851.
    if (!gamepad?.connected) continue;
    const { buttons, axes } = gamepad;
    for (const [index, bit] of padButtonBits) {
      if (buttons[index]?.pressed) mask |= bit;
    }
    for (let axis = 0; axis < padAxisBits.length; axis += 1) {
      const value = axes[axis] ?? 0;
      if (value < -PAD_AXIS_THRESHOLD) mask |= padAxisBits[axis][0];
      if (value > PAD_AXIS_THRESHOLD) mask |= padAxisBits[axis][1];
    }
  }
  return mask;
}

function readInput() {
  const held = keyboardMask | touchMask.value | readGamepadMask();
  input.keyDown = held & ~previousHeld;
  input.keyHeld = held;
  input.mouseX = mouseX;
  input.mouseY = mouseY;
  input.mouseButtons = mouseButtons;
  previousHeld = held;
  return input;
}

function updateMousePosition(event: PointerEvent) {
  const element = canvas.value;
  if (!element) return;
  const rect = element.getBoundingClientRect();
  if (rect.width === 0 || rect.height === 0) return;
  mouseX = clampToScreen(
    ((event.clientX - rect.left) / rect.width) * PICO8_WIDTH,
    PICO8_WIDTH,
  );
  mouseY = clampToScreen(
    ((event.clientY - rect.top) / rect.height) * PICO8_HEIGHT,
    PICO8_HEIGHT,
  );
}

function clampToScreen(value: number, size: number) {
  return Math.max(0, Math.min(size - 1, Math.floor(value)));
}

function getMouseButtonMask(button: number) {
  return mouseButtonBits[button] ?? 0;
}

function onCanvasPointerMove(event: PointerEvent) {
  if (!gameRunning.value) return;
  updateMousePosition(event);
}

function onCanvasPointerDown(event: PointerEvent) {
  if (!gameRunning.value) return;
  event.preventDefault();
  updateMousePosition(event);
  mouseButtons |= getMouseButtonMask(event.button);
  canvas.value?.setPointerCapture(event.pointerId);
}

function onCanvasPointerUp(event: PointerEvent) {
  updateMousePosition(event);
  mouseButtons &= ~getMouseButtonMask(event.button);
}

function onCanvasPointerCancel() {
  mouseButtons = 0;
}

function onControlPointerDown(bit: number, event: PointerEvent) {
  if (!gameRunning.value) return;
  event.preventDefault();
  touchMask.value |= bit;
  (event.currentTarget as HTMLElement).setPointerCapture?.(event.pointerId);
}

function onControlPointerUp(bit: number, event: PointerEvent) {
  event.preventDefault();
  touchMask.value &= ~bit;
}

function onControlKeyDown(bit: number, event: KeyboardEvent) {
  if (!gameRunning.value || !["Enter", "Space"].includes(event.code)) return;
  event.preventDefault();
  touchMask.value |= bit;
}

function onControlKeyUp(bit: number) {
  touchMask.value &= ~bit;
}

function scheduleAudio(samples: Int16Array) {
  if (!audioContext || !audioGain || samples.length === 0) return;
  const buffer = audioContext.createBuffer(
    1,
    samples.length,
    audioContext.sampleRate,
  );
  const channel = buffer.getChannelData(0);
  for (let index = 0; index < samples.length; index += 1) {
    channel[index] = samples[index] / 32768;
  }
  const source = audioContext.createBufferSource();
  source.buffer = buffer;
  source.connect(audioGain);
  const startAt = Math.max(audioContext.currentTime, nextAudioTime);
  source.start(startAt);
  nextAudioTime = startAt + buffer.duration;
}

function runFrame(timestamp: number) {
  if (!gameRunning.value || !runtime) return;
  frameAccumulator += Math.min(timestamp - lastFrameTime, 250);
  lastFrameTime = timestamp;

  let steps = 0;
  try {
    while (frameAccumulator >= frameDuration && steps < 3) {
      runtime.advance(readInput());
      scheduleAudio(runtime.getAudioSamples());
      frameAccumulator -= frameDuration;
      steps += 1;
    }
    if (steps > 0) runtime.render();
  } catch (error) {
    showPlayError(error);
    return;
  }
  animationFrame = requestAnimationFrame(runFrame);
}

function startLoop() {
  frameDuration = 1000 / (runtime?.frameRate || PICO8_FRAME_RATE);
  lastFrameTime = performance.now();
  frameAccumulator = frameDuration;
  animationFrame = requestAnimationFrame(runFrame);
}

function closeAudio() {
  const context = audioContext;
  audioContext = null;
  audioGain = null;
  nextAudioTime = 0;
  if (context) void context.close().catch(() => {});
}

function resetInput() {
  previousHeld = 0;
  keyboardMask = 0;
  mouseX = 0;
  mouseY = 0;
  mouseButtons = 0;
  touchMask.value = 0;
}

function releaseGame() {
  cancelAnimationFrame(animationFrame);
  animationFrame = 0;
  runtime?.dispose();
  runtime = null;
  closeAudio();
  resetInput();
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

    try {
      audioContext = new AudioContext({
        sampleRate: runtime.audioSampleRate,
      });
    } catch {
      try {
        audioContext = new AudioContext();
      } catch {
        audioContext = null;
      }
    }
    if (audioContext) {
      audioGain = audioContext.createGain();
      audioGain.gain.value = 0.75;
      audioGain.connect(audioContext.destination);
      void audioContext.resume().catch(() => {});
    }

    loading.value = false;
    playSession.start(currentRom);
    if (fullscreenOnPlay.value && stage.value?.requestFullscreen) {
      void stage.value.requestFullscreen().catch(() => {});
    }
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
useEventListener(window, "blur", resetInput);

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
    @quit="onlyQuit"
  >
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
            @pointercancel="onCanvasPointerCancel"
            @contextmenu.prevent
          />
          <div v-if="loading" class="r-v2-pico8__loading">
            <RSpinner :size="32" :aria-label="t('common.loading')" />
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
  width: 100%;
  height: 100%;
  display: grid;
  place-items: center;
  align-content: center;
  gap: 20px;
  overflow: auto;
  padding: 24px;
  box-sizing: border-box;
}

.r-v2-pico8__stage:fullscreen {
  background: var(--r-color-canvas-bg);
}

.r-v2-pico8__screen {
  position: relative;
  width: min(78vmin, 640px);
  aspect-ratio: 1;
  flex: 0 0 auto;
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
  gap: 12px;
  padding: 16px;
}

html[data-bp~="xs"] .r-v2-pico8__screen {
  width: min(78vmin, 420px);
}

html[data-bp~="xs"] .r-v2-pico8__controls {
  gap: 16px;
  transform: scale(0.9);
}
</style>
