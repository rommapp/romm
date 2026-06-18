<script setup lang="ts">
// BackendStatusBanner — soft-red connection notice. Invisible while the
// backend is healthy; surfaces a compact, centred toast-style card near the
// top the moment the heartbeat probe (or a request) reports the backend as
// down/broken. Unlike a redirect to /login, the user can keep navigating
// wherever the cached state allows — the card just explains the degraded
// state and the connection layer auto-recovers.
//
// Calling `useServerConnection()` here in setup both gives us the reactive
// `isOffline` flag AND installs the app-wide poll / passive listeners /
// recovery (idempotent). It must run in a setup context so the composable's
// `inject("emitter")` resolves — this component is mounted once, under
// `v-if="isV2"` in RomM.vue, so it covers both the auth and main shells.
import { RBtn, RIcon } from "@v2/lib";
import { useI18n } from "vue-i18n";
import { useServerConnection } from "@/v2/composables/useServerConnection";

defineOptions({ inheritAttrs: false });

const { t } = useI18n();
const { isOffline, retryNow } = useServerConnection();
</script>

<template>
  <Transition name="r-backend-banner">
    <div v-if="isOffline" class="r-backend-banner" role="alert">
      <RIcon
        icon="mdi-lan-disconnect"
        size="18"
        class="r-backend-banner__icon"
      />
      <span class="r-backend-banner__msg">
        {{ t("common.server-offline-retrying") }}
      </span>
      <RBtn
        size="small"
        variant="text"
        prepend-icon="mdi-refresh"
        class="r-backend-banner__retry"
        @click="retryNow"
      >
        {{ t("common.try-again") }}
      </RBtn>
    </div>
  </Transition>
</template>

<style scoped>
/* Compact toast-style card, centred under the navbar. Soft-red glass: the
   neutral deep-canvas panel tinted lightly with the danger token (no hex
   literals, §X) so text stays legible and the red reads as "soft", not a
   solid alarm bar. */
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
    var(--r-color-canvas-bg-deep)
  );
  border: 1px solid
    color-mix(in srgb, var(--r-color-status-base-danger) 40%, transparent);
  border-radius: var(--r-radius-lg);
  backdrop-filter: blur(18px);
  -webkit-backdrop-filter: blur(18px);
  box-shadow:
    0 10px 28px color-mix(in srgb, black 45%, transparent),
    0 2px 6px color-mix(in srgb, black 30%, transparent);
  color: var(--r-color-fg);
  font-size: 13px;
  line-height: 1.4;
}

.r-backend-banner__icon {
  flex-shrink: 0;
  color: var(--r-color-danger-fg);
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
</style>
