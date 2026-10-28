<script setup lang="ts">
// NotificationHost: v2 toast host. Listens for `snackbarShow` and stacks
// transient glass-card toasts in the top-right (top-centre on mobile).
// Each toast auto-dismisses after `timeout` ms (default 3000) and can be
// closed manually. Unlike v1, which replaced a single v-snackbar on each
// emission, v2 stacks so fast successive messages don't overwrite each
// other. Stored colour/icon fields are preserved so existing emitters work.
import { useEventListener } from "@vueuse/core";
import { onBeforeUnmount, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useEmitterEvent } from "@/composables/useEmitterEvent";
import { TONE_ICONS, type SnackbarTone } from "@/composables/useSnackbar";
import { RIcon } from "@/lib";
import storeNotifications from "@/stores/notifications";
import type { SnackbarStatus } from "@/types/emitter";

defineOptions({ inheritAttrs: false });

const { t } = useI18n();

type Toast = {
  id: number;
  msg: string;
  icon?: string | undefined;
  image?: string | null | undefined;
  tone: SnackbarTone;
  timer?: number | undefined;
};

const toasts = ref<Toast[]>([]);
const notificationStore = storeNotifications();

// The existing v1 emitters pass free-form colour strings ("green", "red",
// "primary", "orange"). Collapse down to four v2 tones for consistent
// styling; unknown colours become `info`.
function toneFromColor(color: string | undefined): SnackbarTone {
  if (!color) return "info";
  const c = color.toLowerCase();
  if (c.includes("green") || c === "success") return "success";
  if (c.includes("red") || c === "error" || c === "danger") return "error";
  if (c.includes("orange") || c.includes("yellow") || c === "warning")
    return "warning";
  return "info";
}

let counter = 1;

function push(status: SnackbarStatus) {
  const tone = toneFromColor(status.color);
  const id = counter++;
  const timeout = status.timeout ?? 3000;
  const toast: Toast = {
    id,
    msg: status.msg,
    icon: status.icon || TONE_ICONS[tone],
    image: status.image,
    tone,
  };
  toasts.value = [...toasts.value, toast];
  notificationStore.add({ ...status, id });
  if (timeout > 0) {
    toast.timer = window.setTimeout(() => dismiss(id), timeout);
  }
}

function dismiss(id: number) {
  const toast = toasts.value.find((t) => t.id === id);
  if (!toast) return;
  if (toast.timer) window.clearTimeout(toast.timer);
  toasts.value = toasts.value.filter((t) => t.id !== id);
  notificationStore.remove(id);
}

const openHandler = (snackbar: SnackbarStatus) => push(snackbar);
useEmitterEvent("snackbarShow", openHandler);

// A fullscreen element is the only thing the browser paints, so the host moves
// inside it: a player that took the screen still gets to show its notices.
const fullscreenHost = ref<HTMLElement | null>(null);
function trackFullscreen() {
  fullscreenHost.value = document.fullscreenElement as HTMLElement | null;
}
useEventListener(document, "fullscreenchange", trackFullscreen);
// A host mounted while a game already owns the screen gets no event of its own.
trackFullscreen();

onBeforeUnmount(() => {
  toasts.value.forEach((t) => t.timer && window.clearTimeout(t.timer));
});
</script>

<template>
  <Teleport :to="fullscreenHost ?? 'body'" :disabled="!fullscreenHost">
    <div class="r-toasts" role="status" aria-live="polite">
      <transition-group name="r-toast">
        <div
          v-for="toast in toasts"
          :key="toast.id"
          class="r-toast"
          :class="[`r-toast--${toast.tone}`]"
          role="alert"
        >
          <img
            v-if="toast.image"
            :src="toast.image"
            alt=""
            class="r-toast__art"
            @error="toast.image = null"
          />
          <RIcon
            v-else-if="toast.icon"
            :icon="toast.icon"
            size="18"
            class="r-toast__icon"
          />
          <span class="r-toast__msg">{{ toast.msg }}</span>
          <button
            type="button"
            class="r-toast__close"
            :aria-label="t('common.dismiss')"
            @click="dismiss(toast.id)"
          >
            <RIcon icon="mdi-close" size="14" />
          </button>
        </div>
      </transition-group>
    </div>
  </Teleport>
</template>

<style scoped>
.r-toasts {
  position: fixed;
  top: calc(var(--r-nav-h, 64px) + 14px);
  right: calc(16px + var(--r-safe-r));
  z-index: var(--r-z-snackbar, 2700);
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-width: min(420px, calc(100vw - 32px));
  pointer-events: none;
}

.r-toast {
  pointer-events: auto;
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  background: var(--r-color-toast-bg);
  border: 1px solid var(--r-color-border-strong);
  border-radius: var(--r-radius-md);
  backdrop-filter: blur(18px);
  box-shadow:
    0 10px 28px color-mix(in srgb, black 45%, transparent),
    0 2px 6px color-mix(in srgb, black 30%, transparent);
  color: var(--r-color-fg);
  font-size: 13px;
  line-height: 1.45;
}

.r-toast__art {
  flex-shrink: 0;
  width: 28px;
  height: 38px;
  border-radius: var(--r-radius-xs, 4px);
  object-fit: cover;
}

/* Tone accents: a tinted icon + a coloured left edge. Keeps the glass
   panel neutral so text stays highly legible. */
/* .r-toast--success { border-left: 3px solid var(--r-color-success); }
.r-toast--error { border-left: 3px solid var(--r-color-danger-fg); }
.r-toast--warning { border-left: 3px solid var(--r-color-warning-fg); }
.r-toast--info { border-left: 3px solid var(--r-color-brand-primary); } */

.r-toast--success .r-toast__icon {
  color: var(--r-color-success);
}
.r-toast--error .r-toast__icon {
  color: var(--r-color-danger-fg);
}
.r-toast--warning .r-toast__icon {
  color: var(--r-color-warning-fg);
}
.r-toast--info .r-toast__icon {
  color: var(--r-color-brand-primary);
}

.r-toast__msg {
  min-width: 0;
  word-break: break-word;
}

.r-toast__close {
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
.r-toast__close:hover {
  background: var(--r-color-surface);
  color: var(--r-color-fg);
}

/* Stack animations: incoming slides in from the right, outgoing fades
   and slides out. */
.r-toast-enter-from {
  opacity: 0;
  transform: translateX(20px);
}
.r-toast-leave-to {
  opacity: 0;
  transform: translateX(20px);
}
.r-toast-enter-active,
.r-toast-leave-active {
  transition:
    opacity var(--r-motion-med) var(--r-motion-ease-out),
    transform var(--r-motion-med) var(--r-motion-ease-out);
}
.r-toast-leave-active {
  position: absolute;
  right: 0;
  left: 0;
}

html[data-bp~="xs"] .r-toasts {
  top: calc(var(--r-nav-h, 64px) + 8px);
  left: 16px;
  right: 16px;
  max-width: none;
  align-items: stretch;
}
</style>
