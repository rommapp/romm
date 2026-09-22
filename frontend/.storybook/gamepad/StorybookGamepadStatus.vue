<script setup lang="ts">
/** Canvas HUD when Gamepad is On; fed by GamepadStoryHost telemetry ref (see telemetry.ts). */
import { computed } from "vue";
import { RECENT_EVENT_FADE_MS } from "./constants";
import type { GamepadTelemetryPayload } from "./telemetry";

defineOptions({ inheritAttrs: false });

const props = defineProps<{
  telemetry: GamepadTelemetryPayload;
}>();

const LEDS = [
  { key: "dpad" as const, label: "D-pad" },
  { key: "stick" as const, label: "Stick" },
  { key: "face" as const, label: "Face" },
  { key: "menu" as const, label: "Menu" },
];

const hasActivity = computed(() => {
  const a = props.telemetry.activity;
  return a.dpad || a.stick || a.face || a.menu;
});

const detailLine = computed(() => {
  const t = props.telemetry;
  if (!t.connected) return "No controller";
  return t.padLabel ?? "Ready";
});

const showCategoryLeds = computed(
  () => props.telemetry.enabled && props.telemetry.connected,
);

const fadeSeconds = RECENT_EVENT_FADE_MS / 1000;
</script>

<template>
  <div
    class="sb-gpad-status"
    data-storybook-gamepad-status
    data-testid="storybook-gamepad-status"
    :title="telemetry.padLabel ?? undefined"
  >
    <div class="sb-gpad-status__main">
      <span class="sb-gpad-status__brand">
        <span
          class="mdi mdi-gamepad-outline sb-gpad-status__icon"
          aria-hidden="true"
        />
        Gamepad
      </span>
      <span
        class="sb-gpad-status__conn"
        :class="{
          'sb-gpad-status__conn--ok': telemetry.connected,
        }"
        :title="
          telemetry.connected
            ? 'Controller connected'
            : 'No controller connected'
        "
      />
      <span
        class="sb-gpad-status__live"
        :class="{
          'sb-gpad-status__live--on': telemetry.connected && hasActivity,
        }"
        title="Lights up when the browser receives pad input"
      />
      <span
        class="sb-gpad-status__line"
        :class="{ 'sb-gpad-status__line--muted': !telemetry.connected }"
      >
        {{ detailLine }}
      </span>
      <span
        v-if="showCategoryLeds"
        class="sb-gpad-status__leds"
        aria-label="Input type"
      >
        <span
          v-for="led in LEDS"
          :key="led.key"
          class="sb-gpad-status__led"
          :class="{ 'sb-gpad-status__led--on': telemetry.activity[led.key] }"
          :title="led.label"
        />
      </span>
    </div>
    <p
      v-if="telemetry.recentEvent"
      :key="telemetry.recentEventSeq"
      class="sb-gpad-status__event"
      :style="{ animationDuration: `${fadeSeconds}s` }"
    >
      Last event: {{ telemetry.recentEvent }}
    </p>
  </div>
</template>

<style scoped>
.sb-gpad-status {
  position: fixed;
  top: 8px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 2147483000;
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 4px;
  max-width: min(480px, calc(100vw - 24px));
  padding: 5px 10px 6px;
  border-radius: 8px;
  border: 1px solid var(--r-color-border);
  background: color-mix(in srgb, var(--r-color-bg-elevated) 92%, transparent);
  box-shadow: 0 4px 16px rgb(0 0 0 / 25%);
  font: 11px/1.25 var(--r-font-family, system-ui, sans-serif);
  color: var(--r-color-fg);
  pointer-events: none;
  cursor: default;
}

html[data-input="pad"] .sb-gpad-status,
html[data-input="pad"] .sb-gpad-status * {
  cursor: default !important;
}

.sb-gpad-status__main {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}

.sb-gpad-status__brand {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
  font-weight: var(--r-font-weight-semibold, 600);
  color: var(--r-color-fg);
}

.sb-gpad-status__icon {
  font-size: 14px;
  line-height: 1;
  opacity: 0.9;
}

.sb-gpad-status__conn,
.sb-gpad-status__live {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
  border: 1px solid var(--r-color-border);
  background: transparent;
  opacity: 0.4;
}

.sb-gpad-status__conn--ok {
  opacity: 1;
  background: var(--r-color-success);
  border-color: var(--r-color-success);
}

.sb-gpad-status__live--on {
  opacity: 1;
  background: var(--r-color-brand-primary);
  border-color: var(--r-color-brand-primary);
  box-shadow: 0 0 0 2px
    color-mix(in srgb, var(--r-color-brand-primary) 40%, transparent);
}

.sb-gpad-status__line {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 0;
}

.sb-gpad-status__line--muted {
  color: var(--r-color-fg-muted);
}

.sb-gpad-status__leds {
  display: flex;
  flex-shrink: 0;
  gap: 3px;
  margin-left: 2px;
}

.sb-gpad-status__led {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  border: 1px solid var(--r-color-border);
  opacity: 0.35;
  background: transparent;
  transition:
    background 80ms ease,
    opacity 80ms ease;
}

.sb-gpad-status__led--on {
  opacity: 1;
  background: var(--r-color-brand-primary);
  border-color: var(--r-color-brand-primary);
}

.sb-gpad-status__event {
  margin: 0;
  padding: 0 2px;
  font-size: 10px;
  line-height: 1.3;
  color: var(--r-color-fg-muted);
  font-family: ui-monospace, monospace;
  animation: sb-gpad-event-fade ease-out forwards;
}

@keyframes sb-gpad-event-fade {
  0% {
    opacity: 1;
  }
  70% {
    opacity: 0.85;
  }
  100% {
    opacity: 0;
  }
}
</style>
