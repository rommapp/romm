<script setup lang="ts">
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
import { usePlaySession } from "@/v2/composables/usePlaySession";
import { usePlayerHero } from "@/v2/composables/usePlayerHero";
import { useSnackbar } from "@/v2/composables/useSnackbar";
import { useUnloadGuard } from "@/v2/composables/useUnloadGuard";
import {
  createPico8Runtime,
  PICO8_FRAME_RATE,
  PICO8_INPUT_BITS,
  type Pico8Runtime,
} from "./pico8Runtime";

const { t } = useI18n();
const playingStore = storePlaying();
const playSession = usePlaySession();
const snackbar = useSnackbar();
const { fullscreenOnPlay } = useFullscreenPref();
const { modality } = useInputModality();

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
let viewAlive = true;

const keyboardMap: Record<string, number> = {
  ArrowLeft: PICO8_INPUT_BITS.left,
  ArrowRight: PICO8_INPUT_BITS.right,
  ArrowUp: PICO8_INPUT_BITS.up,
  ArrowDown: PICO8_INPUT_BITS.down,
  KeyZ: PICO8_INPUT_BITS.a,
  KeyX: PICO8_INPUT_BITS.b,
};

const directionControls = [
  {
    bit: PICO8_INPUT_BITS.up,
    icon: "mdi-menu-up",
    className: "r-v2-pico8__control--up",
    label: "up",
  },
  {
    bit: PICO8_INPUT_BITS.left,
    icon: "mdi-menu-left",
    className: "r-v2-pico8__control--left",
    label: "left",
  },
  {
    bit: PICO8_INPUT_BITS.right,
    icon: "mdi-menu-right",
    className: "r-v2-pico8__control--right",
    label: "right",
  },
  {
    bit: PICO8_INPUT_BITS.down,
    icon: "mdi-menu-down",
    className: "r-v2-pico8__control--down",
    label: "down",
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
  const gamepads = navigator.getGamepads?.() ?? [];
  for (const gamepad of gamepads) {
    if (!gamepad) continue;
    if (gamepad.buttons[14]?.pressed) mask |= PICO8_INPUT_BITS.left;
    if (gamepad.buttons[15]?.pressed) mask |= PICO8_INPUT_BITS.right;
    if (gamepad.buttons[12]?.pressed) mask |= PICO8_INPUT_BITS.up;
    if (gamepad.buttons[13]?.pressed) mask |= PICO8_INPUT_BITS.down;
    if (gamepad.buttons[0]?.pressed) mask |= PICO8_INPUT_BITS.a;
    if (gamepad.buttons[1]?.pressed) mask |= PICO8_INPUT_BITS.b;
    if ((gamepad.axes[0] ?? 0) < -0.5) mask |= PICO8_INPUT_BITS.left;
    if ((gamepad.axes[0] ?? 0) > 0.5) mask |= PICO8_INPUT_BITS.right;
    if ((gamepad.axes[1] ?? 0) < -0.5) mask |= PICO8_INPUT_BITS.up;
    if ((gamepad.axes[1] ?? 0) > 0.5) mask |= PICO8_INPUT_BITS.down;
  }
  return mask;
}

function getInput() {
  const held = keyboardMask | touchMask.value | readGamepadMask();
  const keyDown = held & ~previousHeld;
  previousHeld = held;
  return { keyDown, keyHeld: held, mouseX, mouseY, mouseButtons };
}

function updateMousePosition(event: PointerEvent) {
  const element = canvas.value;
  if (!element) return;
  const rect = element.getBoundingClientRect();
  if (rect.width === 0 || rect.height === 0) return;
  mouseX = Math.max(
    0,
    Math.min(127, Math.floor(((event.clientX - rect.left) / rect.width) * 128)),
  );
  mouseY = Math.max(
    0,
    Math.min(127, Math.floor(((event.clientY - rect.top) / rect.height) * 128)),
  );
}

function getMouseButtonMask(button: number) {
  if (button === 0) return 0x01;
  if (button === 1) return 0x04;
  if (button === 2) return 0x02;
  return 0;
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
    runtime?.audioSampleRate ?? 22050,
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
  const frameDuration = 1000 / (runtime.frameRate || PICO8_FRAME_RATE);
  const elapsed = Math.min(timestamp - lastFrameTime, 250);
  lastFrameTime = timestamp;
  frameAccumulator += elapsed;

  let steps = 0;
  try {
    while (frameAccumulator >= frameDuration && steps < 3) {
      runtime.step(getInput());
      scheduleAudio(runtime.getAudioSamples());
      frameAccumulator -= frameDuration;
      steps += 1;
    }
  } catch (error) {
    showPlayError(error);
    return;
  }
  animationFrame = requestAnimationFrame(runFrame);
}

function startLoop() {
  lastFrameTime = performance.now();
  frameAccumulator = 1000 / (runtime?.frameRate || PICO8_FRAME_RATE);
  animationFrame = requestAnimationFrame(runFrame);
}

function closeAudio() {
  const context = audioContext;
  audioContext = null;
  audioGain = null;
  nextAudioTime = 0;
  if (context) void context.close().catch(() => {});
}

function releaseGame() {
  cancelAnimationFrame(animationFrame);
  animationFrame = 0;
  runtime?.dispose();
  runtime = null;
  closeAudio();
  previousHeld = 0;
  keyboardMask = 0;
  mouseX = 0;
  mouseY = 0;
  mouseButtons = 0;
  touchMask.value = 0;
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

async function onPlay() {
  const currentRom = rom.value;
  if (!currentRom || gameRunning.value) return;

  gameRunning.value = true;
  loading.value = true;
  playingStore.setPlaying(true);
  await nextTick();

  if (!viewAlive || !gameRunning.value) return;
  const canvasElement = canvas.value;
  if (!canvasElement) {
    showPlayError(new Error("PICO-8 canvas is unavailable"));
    return;
  }

  let nextRuntime: Pico8Runtime | null = null;
  try {
    nextRuntime = await createPico8Runtime(canvasElement);
    if (!viewAlive || !gameRunning.value) {
      nextRuntime.dispose();
      nextRuntime = null;
      return;
    }
    const response = await fetch(getDownloadPath({ rom: currentRom }));
    if (!response.ok) throw new Error(`ROM request failed: ${response.status}`);
    const bytes = new Uint8Array(await response.arrayBuffer());
    if (!viewAlive || !gameRunning.value) {
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
    if (!viewAlive || !gameRunning.value) return;
    showPlayError(error);
  }
}

function onlyQuit() {
  releaseGame();
  window.history.back();
}

useEventListener(window, "keydown", onKeyDown);
useEventListener(window, "keyup", onKeyUp);
useEventListener(window, "blur", () => {
  keyboardMask = 0;
  mouseButtons = 0;
  touchMask.value = 0;
});

onMounted(async () => {
  const romResponse = await romApi.getRom({ romId });
  if (!viewAlive) return;
  rom.value = romResponse.data;
  if (modality.value === "pad" || modality.value === "key") {
    await nextTick();
    if (!viewAlive) return;
    focusPlayButton();
  }
});

onBeforeUnmount(() => {
  viewAlive = false;
  releaseGame();
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
            width="128"
            height="128"
            aria-label="PICO-8 game"
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
          aria-label="PICO-8 controls"
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
                control.className,
                {
                  'r-v2-pico8__control--held': touchMask & control.bit,
                },
              ]"
              :aria-label="`PICO-8 ${control.label}`"
              :title="`PICO-8 ${control.label}`"
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
              :aria-label="`PICO-8 ${control.label}`"
              :title="`PICO-8 ${control.label}`"
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
  background: #000;
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
