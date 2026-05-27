<script setup lang="ts">
// NotificationHost — v2 toast host. Listens for `snackbarShow` and stacks
// transient glass-card toasts in the top-right (top-centre on mobile).
// Each toast auto-dismisses after `timeout` ms (default 3000) and can be
// closed manually. Unlike v1 — which replaced a single v-snackbar on each
// emission — v2 stacks so fast successive messages don't overwrite each
// other. Stored colour/icon fields are preserved so existing emitters work.
import { RIcon } from "@v2/lib";
import type { Emitter } from "mitt";
import { inject, onBeforeUnmount, ref } from "vue";
import { useI18n } from "vue-i18n";
import storeNotifications from "@/stores/notifications";
import type { Events, SnackbarStatus } from "@/types/emitter";

defineOptions({ inheritAttrs: false });

const { t } = useI18n();

type ToastTone = "success" | "error" | "warning" | "info";

type Toast = {
  id: number;
  msg: string;
  icon?: string;
  tone: ToastTone;
  timer?: number;
};

const toasts = ref<Toast[]>([]);
const notificationStore = storeNotifications();
const emitter = inject<Emitter<Events>>("emitter");

// The existing v1 emitters pass free-form colour strings ("green", "red",
// "primary", "orange"). Collapse down to four v2 tones for consistent
// styling; unknown colours become `info`.
function toneFromColor(color: string | undefined): ToastTone {
  if (!color) return "info";
  const c = color.toLowerCase();
  if (c.includes("green") || c === "success") return "success";
  if (c.includes("red") || c === "error" || c === "danger") return "error";
  if (c.includes("orange") || c.includes("yellow") || c === "warning")
    return "warning";
  return "info";
}

function iconFor(tone: ToastTone, fallback?: string): string {
  if (fallback) return fallback;
  if (tone === "success") return "mdi-check-circle-outline";
  if (tone === "error") return "mdi-alert-circle-outline";
  if (tone === "warning") return "mdi-alert-outline";
  return "mdi-information-outline";
}

let counter = 1;

function push(status: SnackbarStatus) {
  const tone = toneFromColor(status.color);
  const id = counter++;
  const timeout = status.timeout ?? 3000;
  const toast: Toast = {
    id,
    msg: status.msg,
    icon: iconFor(tone, status.icon),
    tone,
  };
  toasts.value = [...toasts.value, toast];
  notificationStore.add({ ...status, id });
  if (timeout > 0) {
    toast.timer = window.setTimeout(() => dismiss(id), timeout);
  }
}

function dismiss(id: number) {
  const idx = toasts.value.findIndex((t) => t.id === id);
  if (idx < 0) return;
  const toast = toasts.value[idx];
  if (toast.timer) window.clearTimeout(toast.timer);
  toasts.value = toasts.value.filter((t) => t.id !== id);
  notificationStore.remove(id);
}

const openHandler = (snackbar: SnackbarStatus) => push(snackbar);
emitter?.on("snackbarShow", openHandler);
onBeforeUnmount(() => {
  emitter?.off("snackbarShow", openHandler);
  toasts.value.forEach((t) => t.timer && window.clearTimeout(t.timer));
});
</script>

<template>
  <div class="r-v2-toasts" role="status" aria-live="polite">
    <transition-group name="r-v2-toast">
      <div
        v-for="toast in toasts"
        :key="toast.id"
        class="r-v2-toast"
        :class="[`r-v2-toast--${toast.tone}`]"
        role="alert"
      >
        <RIcon
          v-if="toast.icon"
          :icon="toast.icon"
          size="18"
          class="r-v2-toast__icon"
        />
        <span class="r-v2-toast__msg">{{ toast.msg }}</span>
        <button
          type="button"
          class="r-v2-toast__close"
          :aria-label="t('common.dismiss')"
          @click="dismiss(toast.id)"
        >
          <RIcon icon="mdi-close" size="14" />
        </button>
      </div>
    </transition-group>
  </div>
</template>

<style scoped>
.r-v2-toasts {
  position: fixed;
  top: calc(var(--r-nav-h, 64px) + 14px);
  right: 16px;
  z-index: var(--r-z-snackbar, 2700);
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-width: min(420px, calc(100vw - 32px));
  pointer-events: none;
}

.r-v2-toast {
  pointer-events: auto;
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  background: color-mix(
    in srgb,
    var(--r-color-canvas-bg-deep) 92%,
    transparent
  );
  border: 1px solid var(--r-color-border-strong);
  border-radius: var(--r-radius-md);
  backdrop-filter: blur(18px);
  -webkit-backdrop-filter: blur(18px);
  box-shadow:
    0 10px 28px color-mix(in srgb, black 45%, transparent),
    0 2px 6px color-mix(in srgb, black 30%, transparent);
  color: var(--r-color-fg);
  font-size: 13px;
  line-height: 1.45;
}

/* Tone accents — a tinted icon + a coloured left edge. Keeps the glass
   panel neutral so text stays highly legible. */
/* .r-v2-toast--success { border-left: 3px solid var(--r-color-success); }
.r-v2-toast--error { border-left: 3px solid var(--r-color-danger-fg); }
.r-v2-toast--warning { border-left: 3px solid var(--r-color-warning-fg); }
.r-v2-toast--info { border-left: 3px solid var(--r-color-brand-primary); } */

.r-v2-toast--success .r-v2-toast__icon {
  color: var(--r-color-success);
}
.r-v2-toast--error .r-v2-toast__icon {
  color: var(--r-color-danger-fg);
}
.r-v2-toast--warning .r-v2-toast__icon {
  color: var(--r-color-warning-fg);
}
.r-v2-toast--info .r-v2-toast__icon {
  color: var(--r-color-brand-primary);
}

.r-v2-toast__msg {
  min-width: 0;
  word-break: break-word;
}

.r-v2-toast__close {
  appearance: none;
  background: transparent;
  border: 0;
  color: var(--r-color-fg-muted);
  width: 24px;
  height: 24px;
  display: grid;
  place-items: center;
  border-radius: 6px;
  cursor: pointer;
  transition:
    background var(--r-motion-fast) var(--r-motion-ease-out),
    color var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-v2-toast__close:hover {
  background: var(--r-color-surface);
  color: var(--r-color-fg);
}

/* Stack animations — incoming slides in from the right, outgoing fades
   and slides out. */
.r-v2-toast-enter-from {
  opacity: 0;
  transform: translateX(20px);
}
.r-v2-toast-leave-to {
  opacity: 0;
  transform: translateX(20px);
}
.r-v2-toast-enter-active,
.r-v2-toast-leave-active {
  transition:
    opacity var(--r-motion-med) var(--r-motion-ease-out),
    transform var(--r-motion-med) var(--r-motion-ease-out);
}
.r-v2-toast-leave-active {
  position: absolute;
  right: 0;
  left: 0;
}

html[data-bp~="xs"] .r-v2-toasts {
  top: calc(var(--r-nav-h, 64px) + 8px);
  left: 16px;
  right: 16px;
  max-width: none;
  align-items: stretch;
}
</style>
