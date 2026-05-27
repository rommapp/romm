<script setup lang="ts">
// ControllerDebug — live inspector for gamepad input + modality
// tracking. Polls `navigator.getGamepads()` each frame (matches
// `useGamepad`'s cadence) and shows:
//   * status row — input modality + connected-pad count
//   * one panel per connected pad — sticks, buttons, raw axes
//   * Gamepad → keyboard mapping legend (in sync with useGamepad)
//   * keydown feed — every dispatch (real + synthetic) with timestamp
//
// Polling is independent of `useGamepad` — this view is its own read
// path; the real input loop keeps running in the background.
import { RBtn, RIcon } from "@v2/lib";
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import ControllerPad from "@/v2/components/ControllerDebug/ControllerPad.vue";
import type { GamepadSnapshot } from "@/v2/components/ControllerDebug/types";
import SettingsSection from "@/v2/components/Settings/SettingsSection.vue";
import { useInputModality } from "@/v2/composables/useInputModality";

defineOptions({ inheritAttrs: false });

const { t } = useI18n();
const { modality } = useInputModality();

// useGamepad's mapping legend — keep in sync with the composable.
const KEYBIND_LEGEND: { button: string; key: string }[] = [
  { button: "D-pad Up", key: "ArrowUp" },
  { button: "D-pad Down", key: "ArrowDown" },
  { button: "D-pad Left", key: "ArrowLeft" },
  { button: "D-pad Right", key: "ArrowRight" },
  { button: "Left stick", key: "Arrow{Up,Down,Left,Right}" },
  { button: "A / ✕", key: "activate focused (click)" },
  { button: "B / ○", key: "back (or close open modal)" },
  { button: "Back / Share", key: "back (or close open modal)" },
  { button: "Start / Options", key: "open user menu" },
  { button: "LB / L1", key: "← prev AppNav section" },
  { button: "RB / R1", key: "→ next AppNav section" },
];

const pads = ref<GamepadSnapshot[]>([]);
const rafId = ref<number>(0);

interface LogEntry {
  id: number;
  at: number;
  key: string;
  from: "real" | "synthetic";
}
const keyLog = ref<LogEntry[]>([]);
const LOG_CAP = 30;
let logCounter = 1;

const modalityIcon = computed(() => {
  switch (modality.value) {
    case "pad":
      return "mdi-controller";
    case "key":
      return "mdi-keyboard-outline";
    case "touch":
      return "mdi-gesture-tap";
    default:
      return "mdi-mouse-outline";
  }
});

function tick() {
  const list = navigator.getGamepads?.() ?? [];
  pads.value = list
    .filter((p): p is Gamepad => !!p)
    .map((p) => ({
      key: `${p.index}:${p.id}`,
      index: p.index,
      id: p.id,
      mapping: p.mapping || "—",
      connected: p.connected,
      buttons: p.buttons.map((b) => ({ pressed: b.pressed, value: b.value })),
      axes: [...p.axes],
    }));
  rafId.value = requestAnimationFrame(tick);
}

function onKeydown(e: KeyboardEvent) {
  // `isTrusted` is false for KeyboardEvents constructed via `new` and
  // `dispatchEvent` — which is how `useGamepad` fires synthetic keys.
  const from: LogEntry["from"] = e.isTrusted ? "real" : "synthetic";
  keyLog.value = [
    { id: logCounter++, at: Date.now(), key: e.key, from },
    ...keyLog.value,
  ].slice(0, LOG_CAP);
}

function clearLog() {
  keyLog.value = [];
}

onMounted(() => {
  tick();
  window.addEventListener("keydown", onKeydown);
});
onBeforeUnmount(() => {
  cancelAnimationFrame(rafId.value);
  window.removeEventListener("keydown", onKeydown);
});

function formatTime(t: number) {
  const d = new Date(t);
  return `${d.getHours().toString().padStart(2, "0")}:${d.getMinutes().toString().padStart(2, "0")}:${d.getSeconds().toString().padStart(2, "0")}.${d.getMilliseconds().toString().padStart(3, "0")}`;
}
</script>

<template>
  <div class="r-v2-section-stack">
    <!-- Status -->
    <SettingsSection :title="t('rom.status')" icon="mdi-pulse">
      <div class="r-v2-ctrl__status">
        <div class="r-v2-ctrl__status-row">
          <span class="r-v2-ctrl__status-label">
            {{ t("settings.controller-debug-modality") }}
          </span>
          <span class="r-v2-ctrl__pill" :class="`r-v2-ctrl__pill--${modality}`">
            <RIcon :icon="modalityIcon" size="13" />
            {{ modality }}
          </span>
        </div>
        <div class="r-v2-ctrl__status-row">
          <span class="r-v2-ctrl__status-label">
            {{ t("settings.controller-debug-connected-gamepads") }}
          </span>
          <span
            class="r-v2-ctrl__pill"
            :class="
              pads.length > 0
                ? 'r-v2-ctrl__pill--success'
                : 'r-v2-ctrl__pill--muted'
            "
          >
            <RIcon
              :icon="pads.length > 0 ? 'mdi-controller' : 'mdi-controller-off'"
              size="13"
            />
            {{ pads.length }}
          </span>
        </div>
      </div>
    </SettingsSection>

    <!-- No pad — help state -->
    <SettingsSection
      v-if="pads.length === 0"
      :title="t('settings.controller-debug-no-gamepad')"
      icon="mdi-controller-off"
    >
      <div class="r-v2-ctrl__empty">
        <RIcon
          icon="mdi-gamepad-variant-outline"
          size="40"
          color="var(--r-color-fg-faint)"
        />
        <p>{{ t("settings.controller-debug-wake-hint") }}</p>
        <p class="r-v2-ctrl__hint">
          On Linux some pads require <code>evtest</code> /
          <code>joydev</code> permissions.
        </p>
      </div>
    </SettingsSection>

    <!-- One section per connected pad -->
    <SettingsSection
      v-for="pad in pads"
      :key="pad.key"
      :title="pad.id"
      icon="mdi-controller"
    >
      <template #header-actions>
        <span class="r-v2-ctrl__pad-slot">
          {{ t("settings.controller-debug-slot", { n: pad.index }) }}
        </span>
        <span class="r-v2-ctrl__tag">{{ pad.mapping }}</span>
        <span
          class="r-v2-ctrl__pill"
          :class="
            pad.connected
              ? 'r-v2-ctrl__pill--success'
              : 'r-v2-ctrl__pill--danger'
          "
        >
          {{ pad.connected ? t("common.online") : t("common.offline") }}
        </span>
      </template>

      <ControllerPad :pad="pad" />

      <!-- Raw axes fallback (if more than the standard 4 present) -->
      <div v-if="pad.axes.length > 4" class="r-v2-ctrl__axes">
        <div class="r-v2-ctrl__axes-title">
          {{ t("settings.controller-debug-all-axes") }}
        </div>
        <div v-for="(value, i) in pad.axes" :key="i" class="r-v2-ctrl__axis">
          <span class="r-v2-ctrl__axis-idx">Axis {{ i }}</span>
          <div class="r-v2-ctrl__axis-track">
            <div
              class="r-v2-ctrl__axis-fill"
              :style="{
                left: `${50 - Math.abs(value) * 50 * (value < 0 ? 1 : 0)}%`,
                width: `${Math.abs(value) * 50}%`,
              }"
            />
          </div>
          <span class="r-v2-ctrl__axis-value">
            {{ value.toFixed(3) }}
          </span>
        </div>
      </div>
    </SettingsSection>

    <!-- Mapping legend -->
    <SettingsSection
      :title="t('settings.controller-debug-mapping-title')"
      icon="mdi-swap-horizontal"
    >
      <div class="r-v2-ctrl__legend">
        <div
          v-for="bind in KEYBIND_LEGEND"
          :key="bind.button"
          class="r-v2-ctrl__legend-row"
        >
          <span class="r-v2-ctrl__legend-from">{{ bind.button }}</span>
          <RIcon
            icon="mdi-arrow-right-thin"
            size="12"
            color="var(--r-color-fg-faint)"
          />
          <code class="r-v2-ctrl__legend-to">{{ bind.key }}</code>
        </div>
      </div>
    </SettingsSection>

    <!-- Keydown log -->
    <SettingsSection
      :title="t('settings.controller-debug-keyboard-feed-title')"
      icon="mdi-console-line"
    >
      <template #header-actions>
        <RBtn
          size="small"
          variant="text"
          prepend-icon="mdi-delete-outline"
          :disabled="keyLog.length === 0"
          @click="clearLog"
        >
          Clear
        </RBtn>
      </template>
      <p class="r-v2-ctrl__log-hint">
        <strong>synthetic</strong> = dispatched by <code>useGamepad</code>.
        <strong>real</strong> = physical keyboard.
      </p>
      <ul v-if="keyLog.length" class="r-v2-ctrl__log">
        <li
          v-for="entry in keyLog"
          :key="entry.id"
          class="r-v2-ctrl__log-row"
          :class="`r-v2-ctrl__log-row--${entry.from}`"
        >
          <span class="r-v2-ctrl__log-time">{{ formatTime(entry.at) }}</span>
          <span
            class="r-v2-ctrl__pill"
            :class="
              entry.from === 'synthetic'
                ? 'r-v2-ctrl__pill--brand'
                : 'r-v2-ctrl__pill--muted'
            "
          >
            {{ entry.from }}
          </span>
          <code class="r-v2-ctrl__log-key">{{ entry.key }}</code>
        </li>
      </ul>
      <div v-else class="r-v2-ctrl__log-empty">
        {{ t("settings.controller-debug-empty-feed") }}
      </div>
    </SettingsSection>
  </div>
</template>

<style scoped>
/* Status section --------------------------------------------------- */
.r-v2-ctrl__status {
  display: flex;
  flex-direction: column;
}
.r-v2-ctrl__status-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 16px;
  border-bottom: 1px solid var(--r-color-border);
}
.r-v2-ctrl__status-row:last-child {
  border-bottom: none;
}
.r-v2-ctrl__status-label {
  font-size: 11px;
  font-weight: var(--r-font-weight-bold);
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--r-color-fg-muted);
}

/* Shared status pill (matches mock + other v2 status surfaces). */
.r-v2-ctrl__pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 3px 10px;
  border-radius: var(--r-radius-pill);
  font-size: 11px;
  font-weight: var(--r-font-weight-semibold);
  letter-spacing: 0.04em;
  text-transform: uppercase;
  background: var(--r-color-surface);
  border: 1px solid var(--r-color-border);
  color: var(--r-color-fg-muted);
}
.r-v2-ctrl__pill--brand,
.r-v2-ctrl__pill--key,
.r-v2-ctrl__pill--mouse,
.r-v2-ctrl__pill--touch {
  background: color-mix(in srgb, var(--r-color-brand-primary) 12%, transparent);
  border-color: color-mix(
    in srgb,
    var(--r-color-brand-primary) 28%,
    transparent
  );
  color: var(--r-color-brand-primary);
}
.r-v2-ctrl__pill--success,
.r-v2-ctrl__pill--pad {
  background: color-mix(
    in srgb,
    var(--r-color-status-base-success) 12%,
    transparent
  );
  border-color: color-mix(
    in srgb,
    var(--r-color-status-base-success) 28%,
    transparent
  );
  color: var(--r-color-success);
}
.r-v2-ctrl__pill--danger {
  background: color-mix(
    in srgb,
    var(--r-color-status-base-danger) 12%,
    transparent
  );
  border-color: color-mix(
    in srgb,
    var(--r-color-status-base-danger) 28%,
    transparent
  );
  color: var(--r-color-danger);
}
.r-v2-ctrl__pill--muted {
  /* defaults already match */
}

/* Pad section header chips ----------------------------------------- */
.r-v2-ctrl__pad-slot {
  font-family: var(--r-font-family-mono, monospace);
  font-size: 10px;
  color: var(--r-color-fg-muted);
}
.r-v2-ctrl__tag {
  padding: 2px 8px;
  background: var(--r-color-surface);
  border: 1px solid var(--r-color-border);
  border-radius: var(--r-radius-pill);
  font-family: var(--r-font-family-mono, monospace);
  font-size: 10px;
  color: var(--r-color-fg-secondary);
}

/* Empty state ------------------------------------------------------- */
.r-v2-ctrl__empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 40px 16px 32px;
  color: var(--r-color-fg-muted);
  text-align: center;
}
.r-v2-ctrl__empty p {
  margin: 0;
  font-size: 13px;
  color: var(--r-color-fg);
}
.r-v2-ctrl__hint {
  max-width: 420px;
  color: var(--r-color-fg-muted) !important;
  font-size: 12px !important;
}
.r-v2-ctrl__hint code {
  padding: 1px 4px;
  background: var(--r-color-surface);
  border: 1px solid var(--r-color-border);
  border-radius: 3px;
  font-family: var(--r-font-family-mono, monospace);
  font-size: 11px;
}

/* Axes (overflow > 4) ---------------------------------------------- */
.r-v2-ctrl__axes {
  padding: 12px 16px 16px;
  border-top: 1px solid var(--r-color-border);
}
.r-v2-ctrl__axes-title {
  margin: 0 0 8px;
  font-size: 11px;
  font-weight: var(--r-font-weight-bold);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--r-color-fg-muted);
}
.r-v2-ctrl__axis {
  display: grid;
  grid-template-columns: 64px 1fr 64px;
  align-items: center;
  gap: 10px;
  padding: 4px 0;
  font-size: 11px;
}
.r-v2-ctrl__axis-idx {
  color: var(--r-color-fg-muted);
}
.r-v2-ctrl__axis-track {
  position: relative;
  height: 4px;
  background: var(--r-color-surface);
  border-radius: 2px;
}
.r-v2-ctrl__axis-track::after {
  content: "";
  position: absolute;
  left: 50%;
  top: -2px;
  bottom: -2px;
  width: 1px;
  background: var(--r-color-border);
}
.r-v2-ctrl__axis-fill {
  position: absolute;
  top: 0;
  bottom: 0;
  background: var(--r-color-brand-primary);
  border-radius: 2px;
}
.r-v2-ctrl__axis-value {
  font-family: var(--r-font-family-mono, monospace);
  color: var(--r-color-fg-secondary);
  text-align: right;
}

/* Mapping legend --------------------------------------------------- */
.r-v2-ctrl__legend {
  display: grid;
  grid-template-columns: 1fr 1fr;
}
html[data-bp~="xs"] .r-v2-ctrl__legend {
  grid-template-columns: 1fr;
}
.r-v2-ctrl__legend-row {
  display: grid;
  grid-template-columns: 1fr auto 1.4fr;
  gap: 10px;
  align-items: center;
  padding: 10px 14px;
  border-bottom: 1px solid var(--r-color-border);
  font-size: 12px;
}
.r-v2-ctrl__legend-row:last-child,
.r-v2-ctrl__legend-row:nth-last-child(2):nth-child(odd) {
  /* Drop the bottom border for the last row in each column. */
  border-bottom: none;
}
.r-v2-ctrl__legend-from {
  color: var(--r-color-fg-secondary);
  font-weight: var(--r-font-weight-medium);
}
.r-v2-ctrl__legend-to {
  font-family: var(--r-font-family-mono, monospace);
  color: var(--r-color-brand-primary);
  font-size: 11px;
  text-align: left;
}

/* Keydown log ------------------------------------------------------ */
.r-v2-ctrl__log-hint {
  margin: 0;
  padding: 10px 14px;
  font-size: 11px;
  color: var(--r-color-fg-muted);
  border-bottom: 1px solid var(--r-color-border);
}
.r-v2-ctrl__log-hint code {
  padding: 1px 4px;
  background: var(--r-color-surface);
  border-radius: 3px;
  font-family: var(--r-font-family-mono, monospace);
  color: var(--r-color-fg-secondary);
}
.r-v2-ctrl__log {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  max-height: 280px;
  overflow-y: auto;
  scrollbar-width: thin;
}
.r-v2-ctrl__log-row {
  display: grid;
  grid-template-columns: 100px 96px 1fr;
  gap: 12px;
  align-items: center;
  padding: 8px 14px;
  border-bottom: 1px solid var(--r-color-border);
  font-size: 11px;
}
.r-v2-ctrl__log-row:last-child {
  border-bottom: none;
}
.r-v2-ctrl__log-row--synthetic {
  background: color-mix(in srgb, var(--r-color-brand-primary) 6%, transparent);
}
.r-v2-ctrl__log-time {
  font-family: var(--r-font-family-mono, monospace);
  color: var(--r-color-fg-muted);
}
.r-v2-ctrl__log-key {
  font-family: var(--r-font-family-mono, monospace);
  color: var(--r-color-fg);
}
.r-v2-ctrl__log-empty {
  padding: 28px 16px;
  text-align: center;
  color: var(--r-color-fg-muted);
  font-size: 12px;
}
</style>
