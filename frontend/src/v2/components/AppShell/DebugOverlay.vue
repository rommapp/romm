<script setup lang="ts">
// DebugOverlay — developer-facing diagnostic panel pinned bottom-right
// (right side avoids clashing with the browser's own link-preview tooltip).
//
// Gated by `useDebugMode().enabled` (a per-device localStorage toggle in
// Settings → Developer), NOT by `import.meta.env.DEV` — the whole point is
// being able to flip it on against the deployed build to debug the live
// webui fast. It absorbs the old dev-only BreakpointBadge as its first row.
//
// Every value reads from the same canonical sources that drive the app, so
// the panel can never drift from real state:
//   * breakpoint  → useBreakpoint() (the refs behind <html data-bp>)
//   * input       → useInputModality() (the ref behind <html data-input>)
//   * theme       → useThemeMode() (resolved dark/light)
//   * route       → vue-router
//   * gamepad     → native gamepad events + the repo's `gamepad:buttondown`
//   * perf        → @vueuse/core useFps / useMemory
//
// pointer-events are off so the panel never blocks the UI it overlays.
import {
  useEventListener,
  useFps,
  useMemory,
  useWindowSize,
} from "@vueuse/core";
import { computed, onMounted, ref } from "vue";
import { useRoute } from "vue-router";
import { useBreakpoint } from "@/v2/composables/useBreakpoint";
import type { GamepadButtonEventDetail } from "@/v2/composables/useGamepad";
import { useInputModality } from "@/v2/composables/useInputModality";
import { useThemeMode } from "@/v2/composables/useThemeMode";

// — Breakpoint + viewport ------------------------------------------------
const { xs, smAndUp, mdAndUp, lgAndUp, xlAndUp } = useBreakpoint();
const { width, height } = useWindowSize();
const tier = computed(() => {
  if (xlAndUp.value) return "xl";
  if (lgAndUp.value) return "lg";
  if (mdAndUp.value) return "md";
  if (smAndUp.value) return "sm";
  if (xs.value) return "xs";
  return "—";
});

// — Input modality -------------------------------------------------------
const { modality } = useInputModality();

// — Theme ----------------------------------------------------------------
const { isDark } = useThemeMode();
const themeLabel = computed(() => (isDark.value ? "v2-dark" : "v2-light"));

// — Route ----------------------------------------------------------------
const route = useRoute();
const routeName = computed(() =>
  typeof route.name === "string" ? route.name : "—",
);

// — Gamepad + focus ------------------------------------------------------
const padConnected = ref(false);
const lastButton = ref("—");

function refreshPadConnected() {
  const pads = navigator.getGamepads?.() ?? [];
  padConnected.value = pads.some(Boolean);
}

useEventListener(window, "gamepadconnected", () => {
  padConnected.value = true;
});
useEventListener(window, "gamepaddisconnected", refreshPadConnected);
useEventListener(
  window,
  "gamepad:buttondown",
  (e: CustomEvent<GamepadButtonEventDetail>) => {
    lastButton.value = e.detail?.name ?? `#${e.detail?.index ?? "?"}`;
  },
);

// Currently focused element — track via focusin (bubbles, unlike focus).
const focusEl = ref<Element | null>(null);
function describeFocus(el: Element | null): string {
  if (!el || el === document.body || el === document.documentElement)
    return "—";
  const tag = el.tagName.toLowerCase();
  const key = el.getAttribute("data-focus-key");
  if (key) return `${tag}·${key}`;
  const aria = el.getAttribute("aria-label");
  if (aria) return `${tag}·${aria}`;
  const cls =
    typeof el.className === "string" && el.className.trim()
      ? `.${el.className.trim().split(/\s+/)[0]}`
      : "";
  return `${tag}${cls}`;
}
const focusLabel = computed(() => describeFocus(focusEl.value));
useEventListener(document, "focusin", () => {
  focusEl.value = document.activeElement;
});
useEventListener(document, "focusout", () => {
  focusEl.value = document.activeElement;
});

// — Performance ----------------------------------------------------------
const fps = useFps();
const { isSupported: memSupported, memory } = useMemory();
const heapMb = computed(() =>
  memory.value ? Math.round(memory.value.usedJSHeapSize / 1048576) : null,
);

onMounted(() => {
  refreshPadConnected();
  focusEl.value = document.activeElement;
});
</script>

<template>
  <div class="r-v2-debug" aria-hidden="true">
    <span class="r-v2-debug__heading">debug</span>

    <div class="r-v2-debug__row">
      <span class="r-v2-debug__label">screen</span>
      <span class="r-v2-debug__value">
        <span class="r-v2-debug__accent">{{ tier }}</span>
        {{ Math.round(width) }}×{{ Math.round(height) }}
      </span>
    </div>

    <div class="r-v2-debug__row">
      <span class="r-v2-debug__label">input</span>
      <span class="r-v2-debug__value r-v2-debug__accent">{{ modality }}</span>
    </div>

    <div class="r-v2-debug__row">
      <span class="r-v2-debug__label">theme</span>
      <span class="r-v2-debug__value">{{ themeLabel }}</span>
    </div>

    <div class="r-v2-debug__row">
      <span class="r-v2-debug__label">route</span>
      <span class="r-v2-debug__value">{{ routeName }} · {{ route.path }}</span>
    </div>

    <div class="r-v2-debug__row">
      <span class="r-v2-debug__label">pad</span>
      <span class="r-v2-debug__value">
        <span :class="padConnected ? 'r-v2-debug__ok' : 'r-v2-debug__off'">
          {{ padConnected ? "on" : "off" }}
        </span>
        · {{ lastButton }}
      </span>
    </div>

    <div class="r-v2-debug__row">
      <span class="r-v2-debug__label">focus</span>
      <span class="r-v2-debug__value">{{ focusLabel }}</span>
    </div>

    <div class="r-v2-debug__row">
      <span class="r-v2-debug__label">perf</span>
      <span class="r-v2-debug__value">
        <span class="r-v2-debug__accent">{{ fps }}</span> fps
        <template v-if="memSupported && heapMb !== null">
          · {{ heapMb }} MB
        </template>
      </span>
    </div>
  </div>
</template>

<style scoped>
.r-v2-debug {
  position: fixed;
  bottom: 8px;
  right: 8px;
  z-index: var(--r-z-snackbar);
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 180px;
  max-width: 280px;
  padding: 6px 10px;
  border-radius: var(--r-radius-md);
  background: var(--r-color-panel);
  border: 1px solid var(--r-color-panel-border);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  font-family: var(--r-font-family-mono);
  font-size: var(--r-font-size-xs);
  line-height: 1.35;
  color: var(--r-color-fg-secondary);
  pointer-events: none;
  user-select: none;
  opacity: 0.95;
}

.r-v2-debug__heading {
  font-weight: var(--r-font-weight-bold);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--r-color-fg-muted);
  margin-bottom: 2px;
}

.r-v2-debug__row {
  display: flex;
  align-items: baseline;
  gap: 8px;
}

.r-v2-debug__label {
  flex: 0 0 auto;
  width: 44px;
  color: var(--r-color-fg-muted);
}

.r-v2-debug__value {
  flex: 1 1 auto;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--r-color-fg);
}

.r-v2-debug__accent {
  font-weight: var(--r-font-weight-bold);
  color: var(--r-color-brand-primary);
}

.r-v2-debug__ok {
  color: var(--r-color-status-base-success);
  font-weight: var(--r-font-weight-bold);
}

.r-v2-debug__off {
  color: var(--r-color-fg-muted);
}

/* Lift clear of the bottom tab bar on small screens. */
html[data-bp~="sm-and-down"] .r-v2-debug {
  bottom: calc(var(--r-bottom-nav-h) + 8px);
}
</style>
