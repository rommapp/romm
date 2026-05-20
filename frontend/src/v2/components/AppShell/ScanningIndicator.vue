<script setup lang="ts">
// ScanningIndicator — small animated pill that appears in the AppNav
// right cluster whenever a library scan is in progress. Two activity
// cues: a travelling shimmer sweep and a soft icon pulse, both on the
// same period so the rhythm reads as deliberate. Click jumps to /scan
// so the user can see the live log.
//
// Hidden on /scan itself (the log is already visible there). Honours
// `prefers-reduced-motion` by dropping the animations but keeping the
// coloured pill so the affordance still reads.
import { RBtn, RTooltip } from "@v2/lib";
import { storeToRefs } from "pinia";
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute } from "vue-router";
import { ROUTES } from "@/plugins/router";
import storeScanning from "@/stores/scanning";

defineOptions({ inheritAttrs: false });

const { t } = useI18n();
const route = useRoute();
const { scanning } = storeToRefs(storeScanning());

const visible = computed(() => scanning.value && route.path !== "/scan");
</script>

<template>
  <Transition name="r-scan-indicator">
    <RTooltip
      v-if="visible"
      :text="t('scan.scanning-library', 'Scanning library — click to view')"
      location="bottom"
    >
      <template #activator="{ props: tooltipProps }">
        <RBtn
          v-bind="tooltipProps"
          prepend-icon="mdi-magnify-scan"
          size="small"
          variant="text"
          class="r-scan-indicator"
          :to="{ name: ROUTES.SCAN }"
          :aria-label="t('scan.scanning-library', 'Scanning library')"
        >
          {{ t("scan.scanning", "Scanning") }}
        </RBtn>
      </template>
    </RTooltip>
  </Transition>
</template>

<style scoped>
/* Brand-tinted pill with two activity cues: a travelling shimmer
   sweep behind the content (::before pseudo) and a soft icon pulse.
   `isolation: isolate` keeps the shimmer from leaking into any
   ancestor backdrop-filter layer (same trick as the nav sub-pill). */
.r-scan-indicator {
  background: color-mix(
    in srgb,
    var(--r-color-brand-primary) 14%,
    transparent
  ) !important;
  border: 1px solid
    color-mix(in srgb, var(--r-color-brand-primary) 38%, transparent) !important;
  color: var(--r-color-brand-primary) !important;
  position: relative;
  overflow: hidden;
  isolation: isolate;
}
.r-scan-indicator::before {
  content: "";
  position: absolute;
  inset: 0;
  background: linear-gradient(
    90deg,
    transparent 0%,
    color-mix(in srgb, var(--r-color-brand-primary) 26%, transparent) 50%,
    transparent 100%
  );
  transform: translateX(-100%);
  animation: r-scan-indicator-shimmer 1.6s linear infinite;
  pointer-events: none;
  z-index: 0;
}
@keyframes r-scan-indicator-shimmer {
  0% {
    transform: translateX(-100%);
  }
  100% {
    transform: translateX(100%);
  }
}

/* Vuetify renders the icon inside `.v-btn__prepend > .v-icon`; the
   label inside `.v-btn__content`. Both ride above the shimmer via
   z-index so the gradient travels behind them. */
.r-scan-indicator :deep(.v-btn__prepend),
.r-scan-indicator :deep(.v-btn__content) {
  position: relative;
  z-index: 1;
}
.r-scan-indicator :deep(.v-btn__prepend .v-icon) {
  animation: r-scan-indicator-pulse 1.6s ease-in-out infinite;
  transform-origin: center;
}
@keyframes r-scan-indicator-pulse {
  0%,
  100% {
    transform: scale(1);
    opacity: 0.85;
  }
  50% {
    transform: scale(1.15);
    opacity: 1;
  }
}

/* Enter / leave — opacity + slide-in from the right side (matches
   the pill's home in the AppNav right cluster). easeBack overshoot
   matches the sub-pill so navbar micro-interactions feel related. */
.r-scan-indicator-enter-active {
  transition:
    opacity var(--r-motion-med) var(--r-motion-ease-out),
    transform var(--r-motion-med) var(--r-motion-ease-back);
}
.r-scan-indicator-leave-active {
  transition:
    opacity var(--r-motion-fast) var(--r-motion-ease-out),
    transform var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-scan-indicator-enter-from,
.r-scan-indicator-leave-to {
  opacity: 0;
  transform: translateX(10px) scale(0.9);
}

@media (prefers-reduced-motion: reduce) {
  .r-scan-indicator::before,
  .r-scan-indicator :deep(.v-btn__prepend .v-icon) {
    animation: none;
  }
}
</style>
