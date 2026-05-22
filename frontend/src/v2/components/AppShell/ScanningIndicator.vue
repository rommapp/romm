<script setup lang="ts">
// ScanningIndicator — live status pill that appears in the AppNav
// right cluster whenever a library scan is in progress.
//
// Three signals stack inside the pill:
//   * a spinner on the leading edge for "something is happening",
//   * a counter (scanned / total when known, scanned-only as soon
//     as the backend has reported a total ≥ scanned),
//   * a thin progress bar pinned to the bottom edge — determinate
//     when `total_roms` is known, indeterminate otherwise (the
//     scanner discovers files as it goes, so totals show up after
//     the first platform finishes).
//
// Click jumps to /scan so the user can inspect the live log.
// Hidden on /scan itself. Honours `prefers-reduced-motion` by
// dropping the shimmer + pulse animations; the spinner + progress
// bar keep moving since they communicate live data, not affect.
import { RProgressLinear, RSpinner, RTooltip } from "@v2/lib";
import { storeToRefs } from "pinia";
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute } from "vue-router";
import { ROUTES } from "@/plugins/router";
import storeScanning from "@/stores/scanning";

defineOptions({ inheritAttrs: false });

const { t } = useI18n();
const route = useRoute();
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

const counterLabel = computed(() => {
  if (!hasTotal.value) return null;
  return `${scanned.value} / ${total.value}`;
});

const tooltipText = computed(() => {
  const base = t("scan.scanning-library", "Scanning library — click to view");
  return counterLabel.value ? `${base} (${counterLabel.value} ROMs)` : base;
});
</script>

<template>
  <Transition name="r-scan-indicator">
    <RTooltip v-if="visible" :text="tooltipText" location="bottom">
      <template #activator="{ props: tooltipProps }">
        <router-link
          v-bind="tooltipProps"
          :to="{ name: ROUTES.SCAN }"
          class="r-scan-indicator"
          :aria-label="tooltipText"
        >
          <span class="r-scan-indicator__row">
            <RSpinner size="14" color="primary" />
            <span class="r-scan-indicator__label">
              {{ t("scan.scanning", "Scanning") }}
            </span>
            <span v-if="counterLabel" class="r-scan-indicator__counter">
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
  height: 32px;
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

/* Content row sits above the bottom-pinned progress bar — top-aligned
   inside the pill so the counter's baseline matches the spinner's. */
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

/* Tabular numerals so the counter doesn't shimmy as digits tick up. */
.r-scan-indicator__counter {
  font-variant-numeric: tabular-nums;
  font-size: 11px;
  padding: 1px 6px;
  border-radius: var(--r-radius-pill);
  background: color-mix(in srgb, var(--r-color-brand-primary) 22%, transparent);
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
