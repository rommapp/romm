<script setup lang="ts">
// SummaryStatsSection — v2-native rebuild of v1
// `Settings/ServerStats/SummaryStats.vue`. 6-card mock-faithful grid
// inside a SettingsSection: each card is a simple icon + big number +
// uppercase label.
import { RIcon } from "@v2/lib";
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import { formatBytes } from "@/utils";
import SettingsSection from "@/v2/components/Settings/SettingsSection.vue";

defineOptions({ inheritAttrs: false });

interface Props {
  stats: {
    PLATFORMS: number;
    ROMS: number;
    SAVES: number;
    STATES: number;
    SCREENSHOTS: number;
    TOTAL_FILESIZE_BYTES: number;
  };
}
const props = defineProps<Props>();

const { t } = useI18n();

interface StatCard {
  icon: string;
  value: string;
  label: string;
}

const cards = computed<StatCard[]>(() => [
  {
    icon: "mdi-controller",
    value: props.stats.PLATFORMS.toLocaleString(),
    label: t("common.platforms"),
  },
  {
    icon: "mdi-disc",
    value: props.stats.ROMS.toLocaleString(),
    label: t("settings.games-label"),
  },
  {
    icon: "mdi-content-save",
    value: props.stats.SAVES.toLocaleString(),
    label: t("settings.saves"),
  },
  {
    icon: "mdi-file-cabinet",
    value: props.stats.STATES.toLocaleString(),
    label: t("settings.states"),
  },
  {
    icon: "mdi-image-multiple-outline",
    value: props.stats.SCREENSHOTS.toLocaleString(),
    label: t("settings.screenshots"),
  },
  {
    icon: "mdi-harddisk",
    value: formatBytes(props.stats.TOTAL_FILESIZE_BYTES, 1),
    label: t("common.size-on-disk"),
  },
]);
</script>

<template>
  <SettingsSection :title="t('settings.summary')" icon="mdi-chart-bar">
    <div class="r-v2-stats-summary">
      <div
        v-for="card in cards"
        :key="card.label"
        class="r-v2-stats-summary__card"
      >
        <RIcon :icon="card.icon" size="22" />
        <div class="r-v2-stats-summary__value">{{ card.value }}</div>
        <div class="r-v2-stats-summary__label">{{ card.label }}</div>
      </div>
    </div>
  </SettingsSection>
</template>

<style scoped>
.r-v2-stats-summary {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  padding: 16px;
}
html[data-bp~="sm-and-down"] .r-v2-stats-summary {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}
html[data-bp~="xs"] .r-v2-stats-summary {
  grid-template-columns: minmax(0, 1fr);
}

.r-v2-stats-summary__card {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
  padding: 16px;
  background: var(--r-color-surface);
  border: 1px solid var(--r-color-border);
  border-radius: 10px;
  color: var(--r-color-fg-muted);
}

.r-v2-stats-summary__value {
  font-size: 28px;
  font-weight: 800;
  line-height: 1.1;
  color: var(--r-color-fg);
  font-variant-numeric: tabular-nums;
}

.r-v2-stats-summary__label {
  font-size: 11px;
  font-weight: var(--r-font-weight-semibold);
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--r-color-fg-muted);
}
</style>
