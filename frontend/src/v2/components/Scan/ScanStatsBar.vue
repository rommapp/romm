<script setup lang="ts">
// ScanStatsBar — floating bottom panel that surfaces the live scan
// progress (platforms / roms / firmware) and the abort action. Same
// shell pattern as Gallery's SelectionBar: fixed `bottom`, slides up
// when relevant, glass blur surface, brand-accent typography.
//
// Visibility:
//   * Scan running           → always visible
//   * Scan finished, results → visible until the user dismisses, so
//                              they can read the final counters or
//                              spot the abort if they want to retry
//
// Lives off-canvas (transform: translateY) so animation cost is zero
// when idle. Pointer-events drop to `none` while hidden so it never
// catches stray clicks under the log.
import { RBtn, RIcon, RProgressLinear, RTooltip } from "@v2/lib";
import { storeToRefs } from "pinia";
import { computed, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import storeScanning from "@/stores/scanning";

defineOptions({ inheritAttrs: false });

defineProps<{
  /** Disable the abort button (no scan in flight). */
  scanDisabled?: boolean;
}>();

const emit = defineEmits<{
  (e: "stop"): void;
}>();

const { t } = useI18n();
const { scanning, scanningPlatforms, scanStats } = storeToRefs(storeScanning());

// The user can dismiss the bar after a scan completes. The flag
// auto-resets the next time a scan starts so a new run brings the bar
// back without manual intervention.
const dismissed = ref(false);
watch(scanning, (next) => {
  if (next) dismissed.value = false;
});

const visible = computed(() => {
  if (dismissed.value && !scanning.value) return false;
  return scanning.value || scanningPlatforms.value.length > 0;
});

// Counters — `total` lags `scanned` during platform discovery; clamp so
// the bar never shows a >100% bar or a "going backwards" total.
const scanned = computed(() => scanStats.value.scanned_roms ?? 0);
const total = computed(() =>
  Math.max(scanStats.value.total_roms ?? 0, scanned.value),
);
const hasTotal = computed(() => total.value > 0);
const progress = computed(() =>
  hasTotal.value ? Math.min(100, (scanned.value / total.value) * 100) : 0,
);

const stats = computed(() => ({
  platforms: {
    scanned: scanStats.value.scanned_platforms ?? 0,
    total: scanStats.value.total_platforms ?? 0,
    new: scanStats.value.new_platforms ?? 0,
    identified: Math.min(
      scanStats.value.identified_platforms ?? 0,
      scanStats.value.scanned_platforms ?? 0,
    ),
  },
  roms: {
    scanned: scanStats.value.scanned_roms ?? 0,
    total: scanStats.value.total_roms ?? 0,
    new: scanStats.value.new_roms ?? 0,
    identified: Math.min(
      scanStats.value.identified_roms ?? 0,
      scanStats.value.scanned_roms ?? 0,
    ),
  },
  firmware: {
    scanned: scanStats.value.scanned_firmware ?? 0,
    new: scanStats.value.new_firmware ?? 0,
  },
}));

function onStop() {
  emit("stop");
}

function onDismiss() {
  dismissed.value = true;
}
</script>

<template>
  <div
    class="r-v2-stats-bar"
    :class="{ 'r-v2-stats-bar--visible': visible }"
    :aria-hidden="!visible"
  >
    <div class="r-v2-stats-bar__panel">
      <!-- Status: spinner pulses while running, check mark when done. -->
      <div class="r-v2-stats-bar__status">
        <span
          class="r-v2-stats-bar__pulse"
          :class="{ 'r-v2-stats-bar__pulse--done': !scanning }"
        />
        <span class="r-v2-stats-bar__status-label">
          {{
            scanning
              ? t("scan.scanning", "Scanning")
              : t("scan.scan-complete", "Scan complete")
          }}
        </span>
      </div>

      <!-- Counter cluster — platforms, roms, firmware as small chips. -->
      <div class="r-v2-stats-bar__counters">
        <RTooltip
          :text="
            t('scan.platforms-scanned-with-details', {
              n_scanned_platforms: stats.platforms.scanned,
              n_total_platforms: stats.platforms.total,
              n_new_platforms: stats.platforms.new,
              n_identified_platforms: stats.platforms.identified,
            })
          "
          location="top"
        >
          <template #activator="{ props: tipProps }">
            <span v-bind="tipProps" class="r-v2-stats-bar__chip">
              <RIcon icon="mdi-controller" size="14" />
              <span class="r-v2-stats-bar__chip-num">
                {{ stats.platforms.scanned }}
              </span>
              <span
                v-if="stats.platforms.total"
                class="r-v2-stats-bar__chip-den"
              >
                /{{ stats.platforms.total }}
              </span>
            </span>
          </template>
        </RTooltip>

        <RTooltip
          :text="
            t('scan.roms-scanned-with-details', {
              n_scanned_roms: stats.roms.scanned,
              n_total_roms: stats.roms.total,
              n_new_roms: stats.roms.new,
              n_identified_roms: stats.roms.identified,
            })
          "
          location="top"
        >
          <template #activator="{ props: tipProps }">
            <span v-bind="tipProps" class="r-v2-stats-bar__chip">
              <RIcon icon="mdi-disc" size="14" />
              <span class="r-v2-stats-bar__chip-num">
                {{ stats.roms.scanned }}
              </span>
              <span v-if="stats.roms.total" class="r-v2-stats-bar__chip-den">
                /{{ stats.roms.total }}
              </span>
            </span>
          </template>
        </RTooltip>

        <RTooltip
          v-if="stats.firmware.scanned > 0"
          :text="
            t('scan.firmware-scanned-with-details', {
              n_scanned_firmware: stats.firmware.scanned,
              n_new_firmware: stats.firmware.new,
            })
          "
          location="top"
        >
          <template #activator="{ props: tipProps }">
            <span
              v-bind="tipProps"
              class="r-v2-stats-bar__chip r-v2-stats-bar__chip--alt"
            >
              <RIcon icon="mdi-memory" size="14" />
              <span class="r-v2-stats-bar__chip-num">
                {{ stats.firmware.scanned }}
              </span>
            </span>
          </template>
        </RTooltip>
      </div>

      <!-- Trailing actions — abort while running, dismiss when done. -->
      <div class="r-v2-stats-bar__actions">
        <RTooltip
          v-if="scanning"
          :text="t('scan.abort', 'Abort scan')"
          location="top"
        >
          <template #activator="{ props: tipProps }">
            <RBtn
              v-bind="tipProps"
              icon="mdi-stop-circle-outline"
              variant="text"
              color="danger"
              :disabled="scanDisabled"
              :aria-label="t('scan.abort', 'Abort scan')"
              @click="onStop"
            />
          </template>
        </RTooltip>
        <RTooltip v-else :text="t('common.dismiss', 'Dismiss')" location="top">
          <template #activator="{ props: tipProps }">
            <RBtn
              v-bind="tipProps"
              icon="mdi-close"
              variant="text"
              :aria-label="t('common.dismiss', 'Dismiss')"
              @click="onDismiss"
            />
          </template>
        </RTooltip>
      </div>

      <!-- Determinate progress bar pinned to the bottom edge — same
           pattern as the navbar ScanningIndicator. Indeterminate while
           totals are still being discovered. -->
      <RProgressLinear
        v-if="scanning"
        class="r-v2-stats-bar__progress"
        :indeterminate="!hasTotal"
        :model-value="progress"
        :height="2"
        color="primary"
        :rounded="false"
      />
    </div>
  </div>
</template>

<style scoped>
.r-v2-stats-bar {
  position: fixed;
  left: 50%;
  bottom: max(24px, env(safe-area-inset-bottom, 0));
  transform: translate(-50%, calc(100% + 32px));
  z-index: 8;
  pointer-events: none;
  transition: transform var(--r-motion-mid) var(--r-motion-ease-out);
  @media (prefers-reduced-motion: reduce) {
    transition: none;
  }
}
.r-v2-stats-bar--visible {
  transform: translate(-50%, 0);
  pointer-events: auto;
}

/* Glass pill — same vocabulary as SelectionBar. Border + inset highlight
   + heavy drop shadow over the blurred backdrop. */
.r-v2-stats-bar__panel {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: 16px;
  padding: 8px 8px 8px 16px;
  border-radius: var(--r-radius-pill);
  background: var(--r-color-panel);
  border: 1px solid var(--r-color-panel-border);
  box-shadow:
    0 12px 32px color-mix(in srgb, black 32%, transparent),
    0 0 0 1px color-mix(in srgb, white 4%, transparent) inset;
  backdrop-filter: blur(18px) saturate(140%);
  -webkit-backdrop-filter: blur(18px) saturate(140%);
  overflow: hidden;
}

.r-v2-stats-bar__status {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: var(--r-font-weight-semibold);
  color: var(--r-color-brand-primary);
  white-space: nowrap;
}
.r-v2-stats-bar__status-label {
  letter-spacing: 0.02em;
}

/* Brand-tinted pulse — the live signal. Drops to a green-success tint
   + stops animating when the scan is complete. */
.r-v2-stats-bar__pulse {
  position: relative;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--r-color-brand-primary);
  box-shadow: 0 0 0 0
    color-mix(in srgb, var(--r-color-brand-primary) 65%, transparent);
  animation: r-v2-stats-pulse 1.6s ease-out infinite;
}
.r-v2-stats-bar__pulse--done {
  background: var(--r-color-success);
  box-shadow: none;
  animation: none;
}
@keyframes r-v2-stats-pulse {
  0% {
    box-shadow: 0 0 0 0
      color-mix(in srgb, var(--r-color-brand-primary) 65%, transparent);
  }
  100% {
    box-shadow: 0 0 0 12px
      color-mix(in srgb, var(--r-color-brand-primary) 0%, transparent);
  }
}
@media (prefers-reduced-motion: reduce) {
  .r-v2-stats-bar__pulse {
    animation: none;
  }
}

.r-v2-stats-bar__counters {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.r-v2-stats-bar__chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  border-radius: var(--r-radius-pill);
  background: color-mix(in srgb, var(--r-color-brand-primary) 18%, transparent);
  color: var(--r-color-brand-primary);
  font-size: 12px;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
  cursor: help;
}
.r-v2-stats-bar__chip--alt {
  background: color-mix(
    in srgb,
    var(--r-color-status-base-success) 18%,
    transparent
  );
  color: var(--r-color-success);
}
.r-v2-stats-bar__chip-num {
  font-weight: var(--r-font-weight-semibold);
}
.r-v2-stats-bar__chip-den {
  opacity: 0.7;
}

.r-v2-stats-bar__actions {
  display: inline-flex;
  align-items: center;
}

.r-v2-stats-bar__progress {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
}

/* Mobile — drop horizontal padding + shrink the status label so the
   bar fits cleanly within narrow viewports. */
html[data-bp~="xs"] .r-v2-stats-bar__panel {
  gap: 10px;
  padding: 6px 6px 6px 12px;
}
html[data-bp~="xs"] .r-v2-stats-bar__status-label {
  display: none;
}
</style>
