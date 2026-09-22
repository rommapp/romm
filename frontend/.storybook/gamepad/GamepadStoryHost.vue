<script setup lang="ts">
/**
 * Central preview shell for the gamepad POC.
 *
 * - Props `enabled` comes from withGamepad (toolbar global or parameters.gamepad).
 * - RAF loop + gamepadconnected events → telemetry.ts → StorybookGamepadStatus (top of canvas).
 * - When enabled, mounts GamepadInputLayer so stories receive RomM pad → focus/click translation.
 * - On enabled toggles only, emits GAMEPAD_TOOLBAR_LABEL_EVENT so manager.ts can show 🎮 Off/On
 *   (live pad name and input stay on the canvas bar, not in the manager toolbar).
 */
import { addons } from "storybook/preview-api";
import { computed, onBeforeUnmount, onMounted, ref, toRef, watch } from "vue";
import GamepadInputLayer from "./GamepadInputLayer.vue";
import StorybookGamepadStatus from "./StorybookGamepadStatus.vue";
import { GAMEPAD_TOOLBAR_LABEL_EVENT, MAX_PAD_LABEL_LEN } from "./constants";
import {
  buildTelemetryPayload,
  createActivityTracker,
  findFirstUsablePad,
  type GamepadTelemetryPayload,
} from "./telemetry";
import { fallbackGamepadToolbarLabel } from "./toolbarSync";

defineOptions({ inheritAttrs: false });

const props = defineProps<{
  enabled: boolean;
}>();

const enabled = toRef(props, "enabled");
const activityTracker = createActivityTracker();

const padConnected = ref(false);

// Install while the toolbar is On even before Chrome exposes a pad
// (first button press); connection state is for the status bar only.
const layerActive = computed(() => enabled.value);

const emptyActivity = (): GamepadTelemetryPayload["activity"] => ({
  dpad: false,
  stick: false,
  face: false,
  menu: false,
});

const telemetry = ref<GamepadTelemetryPayload>({
  enabled: false,
  connected: false,
  padLabel: null,
  padIndex: null,
  activity: emptyActivity(),
  recentEvent: null,
  recentEventSeq: 0,
});

let rafId = 0;
let lastToolbarLabel = "";

function syncToolbarForEnabled(on: boolean) {
  const label = fallbackGamepadToolbarLabel(on);
  if (label === lastToolbarLabel) return;
  lastToolbarLabel = label;
  try {
    addons.getChannel().emit(GAMEPAD_TOOLBAR_LABEL_EVENT, label);
  } catch {
    /* noop */
  }
}

function refreshTelemetry() {
  try {
    const now = performance.now();
    const pad = findFirstUsablePad();
    padConnected.value = pad !== null;
    const activity = activityTracker.tick(pad, now);
    telemetry.value = buildTelemetryPayload(
      enabled.value,
      pad,
      activity,
      activityTracker.getRecentEvent(),
      MAX_PAD_LABEL_LEN,
    );
  } catch {
    // Gamepad API unavailable (e.g. happy-dom in storybook:test).
  }
}

function tick() {
  refreshTelemetry();
  rafId = requestAnimationFrame(tick);
}

function onPadChange() {
  if (!findFirstUsablePad()) activityTracker.reset();
  refreshTelemetry();
}

onMounted(() => {
  refreshTelemetry();
  tick();
  window.addEventListener("gamepadconnected", onPadChange);
  window.addEventListener("gamepaddisconnected", onPadChange);
});

onBeforeUnmount(() => {
  cancelAnimationFrame(rafId);
  window.removeEventListener("gamepadconnected", onPadChange);
  window.removeEventListener("gamepaddisconnected", onPadChange);
  activityTracker.reset();
});

watch(
  enabled,
  (on) => {
    if (!on) activityTracker.reset();
    syncToolbarForEnabled(on);
    refreshTelemetry();
  },
  { immediate: true },
);
</script>

<template>
  <StorybookGamepadStatus v-if="enabled" :telemetry="telemetry" />
  <GamepadInputLayer v-if="layerActive" />
  <slot />
</template>
