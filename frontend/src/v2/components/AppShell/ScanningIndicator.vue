<script setup lang="ts">
// Top-bar pill shown during a library scan, linking to /scan. The progress bar
// is indeterminate until the scanner reports a total, which it learns as it goes.
import { RTooltip } from "@v2/lib";
import { storeToRefs } from "pinia";
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute } from "vue-router";
import { ROUTES } from "@/plugins/router";
import storeScanning from "@/stores/scanning";
import { toBrowserLocale } from "@/utils";
import NavStatusPill from "@/v2/components/AppShell/NavStatusPill.vue";
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
  <Transition name="r-nav-status-pill">
    <RTooltip
      v-if="visible"
      :text="t('scan.scanning-library')"
      location="bottom"
    >
      <template #activator="{ props: tooltipProps }">
        <NavStatusPill
          v-bind="tooltipProps"
          :to="{ name: ROUTES.SCAN }"
          :label="t('scan.scanning')"
          icon="mdi-radar"
          :counter="counterLabel"
          :progress="hasTotal ? progress : null"
          :aria-label="t('scan.scanning-library')"
        />
      </template>
    </RTooltip>
  </Transition>
</template>
