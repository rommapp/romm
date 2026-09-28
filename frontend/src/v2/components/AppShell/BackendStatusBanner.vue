<script setup lang="ts">
// BackendStatusBanner — soft-red connection notice. Invisible while the
// backend is healthy; surfaces a compact, centred toast-style card near the
// top the moment the heartbeat probe (or a request) reports the backend as
// down/broken. Unlike a redirect to /login, the user can keep navigating
// wherever the cached state allows — the card just explains the degraded
// state and the connection layer auto-recovers.
//
// Calling `useServerConnection()` here in <script setup> both gives us the
// reactive `isOffline` flag AND triggers the one-time install of the app-wide
// poll / passive DOM-event listeners / recovery watcher (idempotent). This
// component is mounted once, under `v-if="isV2"` in RomM.vue, so it covers both
// the auth and main shells.
//
// When HTTP is up but Socket.IO fell back to polling, `useSocketTransportHealth`
// drives a second message (offline still wins if both are bad).
import { RBtn, RIcon, RTooltip } from "@v2/lib";
import { storeToRefs } from "pinia";
import { computed, inject } from "vue";
import { useI18n } from "vue-i18n";
import storePlaying from "@/stores/playing";
import { backendStatusBannerStoryKey } from "@/v2/components/AppShell/backendStatusBannerStoryKey";
import { useDelayedFlag } from "@/v2/composables/useDelayedFlag";
import { useServerConnection } from "@/v2/composables/useServerConnection";
import { useSocketTransportHealth } from "@/v2/composables/useSocketTransportHealth";

defineOptions({ inheritAttrs: false });

// Long enough to read before the notice gets out of the way of the game.
const COLLAPSE_MS = 6000;

const { t } = useI18n();
const storyState = inject(backendStatusBannerStoryKey, null);
const { isOffline, retryNow, isWebSocketDegraded, retryWebSocket } = (() => {
  if (storyState) return storyState;
  const server = useServerConnection();
  const transport = useSocketTransportHealth();
  return {
    isOffline: server.isOffline,
    retryNow: server.retryNow,
    isWebSocketDegraded: transport.isWebSocketDegraded,
    retryWebSocket: transport.retryWebSocket,
  };
})();
const { playing } = storeToRefs(storePlaying());

const showWebsocketNotice = computed(
  () => !isOffline.value && isWebSocketDegraded.value,
);

const visible = computed(() => isOffline.value || showWebsocketNotice.value);

const messageKey = computed(() =>
  showWebsocketNotice.value
    ? "common.websocket-unreachable-retrying"
    : "common.server-offline-retrying",
);

const icon = computed(() =>
  showWebsocketNotice.value ? "mdi-web-sync" : "mdi-lan-disconnect",
);

// A notice that cannot be dismissed has no business sitting over a running
// game, so it says its piece and then shrinks to its icon.
const collapsed = useDelayedFlag(
  () => visible.value && playing.value,
  COLLAPSE_MS,
);

function onRetry() {
  if (showWebsocketNotice.value) {
    retryWebSocket();
  } else {
    void retryNow();
  }
}
</script>

<template>
  <Transition name="r-backend-banner">
    <div
      v-if="visible"
      class="r-backend-banner"
      :class="{
        'r-backend-banner--in-game': playing,
        'r-backend-banner--collapsed': collapsed,
      }"
      role="alert"
      :aria-label="collapsed ? t(messageKey) : undefined"
    >
      <!-- Shrunk to its icon, so the message still has to be readable. -->
      <RTooltip
        v-if="collapsed"
        activator="parent"
        location="bottom start"
        open-on-tap
        :text="t(messageKey)"
      />
      <RIcon :icon="icon" size="18" class="r-backend-banner__icon" />
      <Transition name="r-backend-banner-body">
        <div v-if="!collapsed" class="r-backend-banner__body">
          <span class="r-backend-banner__msg">
            {{ t(messageKey) }}
          </span>
          <RBtn
            v-if="!playing"
            size="small"
            variant="text"
            prepend-icon="mdi-refresh"
            class="r-backend-banner__retry"
            @click="onRetry"
          >
            {{ t("common.try-again") }}
          </RBtn>
        </div>
      </Transition>
    </div>
  </Transition>
</template>

<style scoped>
/* Compact toast-style card, centred under the navbar. Soft-red glass: the
   theme-aware toast panel tinted lightly with the danger token (no hex
   literals, §X) so the card flips with the theme (dark-red on dark, soft
   pink on light) and the `fg` text stays legible on both, instead of a
   fixed dark panel that left light-theme text black-on-dark. */
.r-backend-banner {
  position: fixed;
  top: calc(var(--r-nav-h, 58px) + 14px);
  left: 50%;
  transform: translateX(-50%);
  z-index: calc(var(--r-z-snackbar) + 10);
  display: inline-flex;
  align-items: center;
  gap: 10px;
  max-width: min(440px, calc(100vw - 32px));
  padding: 8px 8px 8px 14px;
  background: color-mix(
    in srgb,
    var(--r-color-status-base-danger) 16%,
    var(--r-color-toast-bg)
  );
  border: 1px solid
    color-mix(in srgb, var(--r-color-status-base-danger) 40%, transparent);
  border-radius: var(--r-radius-lg);
  backdrop-filter: blur(18px);
  box-shadow:
    0 10px 28px color-mix(in srgb, black 45%, transparent),
    0 2px 6px color-mix(in srgb, black 30%, transparent);
  color: var(--r-color-fg);
  font-size: 13px;
  line-height: 1.4;
}

/* A running game owns the screen, so the notice moves out of its middle and
   into a corner the player's own toasts leave free. */
.r-backend-banner--in-game {
  top: 16px;
  left: 16px;
  right: auto;
  transform: none;
  max-width: min(420px, calc(100vw - 32px));
  /* The retry button is what pads the right edge out; without it the text
     needs the same room the icon gets. */
  padding: 8px 14px;
}

.r-backend-banner--in-game .r-backend-banner__body {
  white-space: nowrap;
}

.r-backend-banner--collapsed {
  padding: 8px;
}

.r-backend-banner__icon {
  flex-shrink: 0;
  color: var(--r-color-danger-fg);
}

.r-backend-banner__body {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
  overflow: hidden;
}

.r-backend-banner__msg {
  min-width: 0;
}

.r-backend-banner__retry {
  flex-shrink: 0;
  color: var(--r-color-danger-fg);
}

/* Slide + fade down from the top edge. */
.r-backend-banner-enter-active,
.r-backend-banner-leave-active {
  transition:
    opacity var(--r-motion-med) var(--r-motion-ease-out),
    transform var(--r-motion-med) var(--r-motion-ease-out);
}
.r-backend-banner-enter-from,
.r-backend-banner-leave-to {
  opacity: 0;
  transform: translate(-50%, -12px);
}
.r-backend-banner--in-game.r-backend-banner-enter-from,
.r-backend-banner--in-game.r-backend-banner-leave-to {
  transform: translateY(-12px);
}

/* The text slides shut as the notice collapses to its icon. */
.r-backend-banner-body-enter-active,
.r-backend-banner-body-leave-active {
  transition:
    opacity var(--r-motion-med) var(--r-motion-ease-out),
    max-width var(--r-motion-med) var(--r-motion-ease-out);
  max-width: 420px;
}
.r-backend-banner-body-enter-from,
.r-backend-banner-body-leave-to {
  opacity: 0;
  max-width: 0;
}

/* On phones keep it centred but allow the safe full width. */
html[data-bp~="xs"] .r-backend-banner {
  left: 12px;
  right: 12px;
  transform: none;
  max-width: none;
  justify-content: center;
}
html[data-bp~="xs"] .r-backend-banner-enter-from,
html[data-bp~="xs"] .r-backend-banner-leave-to {
  transform: translateY(-12px);
}
html[data-bp~="xs"] .r-backend-banner--in-game {
  left: 12px;
  right: auto;
  max-width: calc(100vw - 24px);
  justify-content: flex-start;
}
</style>
