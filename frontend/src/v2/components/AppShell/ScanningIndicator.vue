<script setup lang="ts">
// Top-bar pill shown during a library scan, linking to /scan. The progress bar
// is indeterminate until the scanner reports a total, which it learns as it goes.
import { RIcon, RProgressLinear, RTooltip } from "@v2/lib";
import { storeToRefs } from "pinia";
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute } from "vue-router";
import { ROUTES } from "@/plugins/router";
import storeScanning from "@/stores/scanning";
import { toBrowserLocale } from "@/utils";
import { useBreakpoint } from "@/v2/composables/useBreakpoint";

defineOptions({ inheritAttrs: false });

const { t, locale } = useI18n();
const route = useRoute();
const { xs } = useBreakpoint();
const { scanning, scanStats } = storeToRefs(storeScanning());

const visible = computed(() => scanning.value && route.path !== "/scan");

// The backend can report `total_roms` lagging behind `scanned_roms`
// (e.g. during platform discovery). Use the max so the displayed
// total never appears to "go backwards" or render a >100% bar.
const scanned = computed(() => scanStats.value.scanned_roms ?? 0);
const total = computed(() =>
  Math.max(scanStats.value.total_roms ?? 0, scanned.value),
);

// Determinate progress only when we actually have a useful total
// (> 0 and ≥ scanned). Otherwise the bar runs indeterminate so the
// affordance still reads as "active".
const hasTotal = computed(() => total.value > 0);
const progress = computed(() =>
  hasTotal.value ? Math.min(100, (scanned.value / total.value) * 100) : 0,
);

// Phones shorten large counts (1.8K / 4.6K) so the pill always fits beside
// the mini player.
const compactCount = computed(
  () =>
    new Intl.NumberFormat(toBrowserLocale(locale.value), {
      notation: "compact",
      maximumFractionDigits: 1,
    }),
);

const counterLabel = computed(() => {
  if (!hasTotal.value) return null;
  const format = (n: number) =>
    xs.value ? compactCount.value.format(n) : String(n);
  return `${format(scanned.value)} / ${format(total.value)}`;
});
</script>

<template>
  <Transition name="r-scan-indicator">
    <RTooltip
      v-if="visible"
      :text="t('scan.scanning-library')"
      location="bottom"
    >
      <template #activator="{ props: tooltipProps }">
        <router-link
          v-bind="tooltipProps"
          :to="{ name: ROUTES.SCAN }"
          class="r-scan-indicator"
          :aria-label="t('scan.scanning-library')"
        >
          <span class="r-scan-indicator__row">
            <span class="r-scan-indicator__label">
              {{ t("scan.scanning") }}
            </span>
            <RIcon
              icon="mdi-radar"
              size="15"
              class="r-scan-indicator__icon"
              aria-hidden="true"
            />
            <span v-if="counterLabel">
              {{ counterLabel }}
            </span>
          </span>

          <!-- Live progress bar pinned to the pill's bottom edge.
               Determinate when totals are known, indeterminate
               otherwise — both modes keep the bar visually busy. -->
          <RProgressLinear
            class="r-scan-indicator__progress"
            :indeterminate="!hasTotal"
            :model-value="progress"
            :height="2"
            color="primary"
            :rounded="false"
            stream
          />
        </router-link>
      </template>
    </RTooltip>
  </Transition>
</template>

<style scoped>
/* Brand-tinted pill matching v2's nav vocabulary (same palette as the
   tab nav sub-pill). `isolation: isolate` keeps the inner bar from
   leaking into any ancestor backdrop-filter layer; `overflow: hidden`
   trims the progress bar's corners against the rounded pill. */
.r-scan-indicator {
  position: relative;
  display: inline-flex;
  flex-direction: column;
  align-items: stretch;
  gap: 0;
  height: var(--r-nav-pill-h);
  padding: 0 12px;
  border-radius: var(--r-radius-pill);
  background: color-mix(in srgb, var(--r-color-brand-primary) 14%, transparent);
  border: 1px solid
    color-mix(in srgb, var(--r-color-brand-primary) 38%, transparent);
  color: var(--r-color-brand-primary);
  font-size: 12px;
  font-weight: var(--r-font-weight-medium);
  line-height: 1;
  text-decoration: none;
  cursor: pointer;
  overflow: hidden;
  isolation: isolate;
  transition:
    background var(--r-motion-fast) var(--r-motion-ease-out),
    border-color var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-scan-indicator:hover {
  background: color-mix(in srgb, var(--r-color-brand-primary) 22%, transparent);
  border-color: color-mix(
    in srgb,
    var(--r-color-brand-primary) 55%,
    transparent
  );
}

/* Content row sits above the bottom-pinned progress bar, with the counter
   centred on the label or radar glyph. */
.r-scan-indicator__row {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  min-width: 0;
  /* Leave a sliver of breathing room above the progress bar without
     shrinking the visible content height. */
  padding-bottom: 2px;
}

.r-scan-indicator__label {
  white-space: nowrap;
}

/* Radar glyph stands in for the label on phones — hidden by default so
   the desktop pill keeps its word. */
.r-scan-indicator__icon {
  display: none;
}
html[data-bp~="xs"] .r-scan-indicator__label {
  display: none;
}
html[data-bp~="xs"] .r-scan-indicator__icon {
  display: inline-flex;
}

/* Pinned to the pill's bottom edge; the pill's `overflow: hidden`
   clips the bar's left / right ends against the rounded corners so
   the fill reads as part of the surface. */
.r-scan-indicator__progress {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
}

/* Enter / leave — opacity + slide-in from the right side, matching
   the prior implementation so navbar micro-interactions feel related. */
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
</style>
